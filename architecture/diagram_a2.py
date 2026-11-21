"""Assignment 2 diagram (kept for the change log). Regenerate architecture/architecture-a2.png:  pip install diagrams && python architecture/diagram.py"""
from diagrams import Cluster, Diagram, Edge
from diagrams.aws.network import Route53, CloudFront, APIGateway, NATGateway, InternetGateway, Endpoint
from diagrams.aws.security import WAF, Cognito, SecretsManager, KMS, ACM, IAMRole
from diagrams.aws.storage import S3
from diagrams.aws.compute import Lambda
from diagrams.aws.database import RDSPostgresqlInstance, RDS
from diagrams.aws.integration import SQS
from diagrams.aws.engagement import SES
from diagrams.aws.management import Cloudwatch, Cloudtrail, CloudwatchAlarm
from diagrams.aws.devtools import XRay
from diagrams.aws.storage import Backup
from diagrams.onprem.client import Users
from diagrams.onprem.vcs import Github
from diagrams.onprem.ci import GithubActions

graph = {"fontsize": "22", "pad": "0.5", "nodesep": "0.55", "ranksep": "0.9", "splines": "spline"}

with Diagram("Online Exams & Assignments Platform (ap-south-1, 2 AZs)", filename="architecture/architecture-a2",
             show=False, direction="TB", graph_attr=graph, outformat="png"):
    users = Users("Students / Tutors /\nAdmins (browser)")

    with Cluster("Edge (global)"):
        dns = Route53("Route 53")
        waf = WAF("AWS WAF\n(rate limit + managed rules)")
        cdn = CloudFront("CloudFront\n+ ACM TLS")

    with Cluster("Identity"):
        cognito = Cognito("Cognito User Pool\nstudents/tutors/admins")

    with Cluster("Regional managed services (multi-AZ by design)"):
        web = S3("S3 frontend\n(private, OAC)")
        api = APIGateway("API Gateway HTTP API\nJWT authorizer + throttling")
        uploads = S3("S3 uploads\nSSE-KMS, versioned,\nlifecycle 5 yr")
        q_upload = SQS("uploads-queue\n+ DLQ")
        q_mark = SQS("marking-queue\n+ DLQ")
        q_notify = SQS("notify-queue\n+ DLQ")
        ses = SES("Amazon SES\nemail")

    with Cluster("VPC 10.0.0.0/16"):
        igw = InternetGateway("IGW")
        s3ep = Endpoint("S3 gateway\nendpoint")
        with Cluster("AZ-a"):
            with Cluster("Public 10.0.0.0/24"):
                nat_a = NATGateway("NAT GW a")
            with Cluster("Private app 10.0.10.0/24"):
                api_a = Lambda("API Lambda")
                workers_a = Lambda("marker / upload-\nprocessor / notifier")
            with Cluster("Private data 10.0.20.0/24"):
                db_a = RDSPostgresqlInstance("RDS PostgreSQL\nPRIMARY")
        with Cluster("AZ-b"):
            with Cluster("Public 10.0.1.0/24"):
                nat_b = NATGateway("NAT GW b")
            with Cluster("Private app 10.0.11.0/24"):
                api_b = Lambda("API Lambda")
                workers_b = Lambda("marker / upload-\nprocessor / notifier")
            with Cluster("Private data 10.0.21.0/24"):
                db_b = RDSPostgresqlInstance("RDS PostgreSQL\nSTANDBY")
        proxy = RDS("RDS Proxy\n(both AZs)")

    with Cluster("Security, ops & DR"):
        secrets = SecretsManager("Secrets Manager\nDB credentials")
        kms = KMS("KMS CMK")
        cw = Cloudwatch("CloudWatch\nlogs/metrics/dashboard")
        alarm = CloudwatchAlarm("Alarms -> SNS ops")
        xray = XRay("X-Ray")
        trail = Cloudtrail("CloudTrail")
        backup = Backup("AWS Backup\nPITR 5 min + monthly 5 yr")

    with Cluster("CI/CD"):
        gh = Github("GitHub repo\n(push to main)")
        gha = GithubActions("GitHub Actions\nOIDC -> IAM role\nterraform apply")

    users >> dns >> cdn
    waf - Edge(style="dashed", label="attached") - cdn
    users >> Edge(label="sign-in (Hosted UI)") >> cognito
    cdn >> Edge(label="/*") >> web
    cdn >> Edge(label="/api/*") >> api
    api - Edge(style="dashed", label="validate JWT") - cognito
    api >> [api_a, api_b]
    users >> Edge(label="presigned POST\n(<=50 MB)", color="darkgreen") >> uploads
    uploads >> Edge(label="ObjectCreated") >> q_upload
    [api_a, api_b] >> proxy >> db_a
    db_a - Edge(label="sync replication", style="dashed") - db_b
    [api_a, api_b] >> Edge(label="submit / release") >> q_mark
    [api_a, api_b] >> q_notify
    q_upload >> workers_a
    q_mark >> workers_b
    q_notify >> workers_a
    workers_a >> ses
    workers_b >> proxy
    cw >> alarm
    nat_a >> igw
    nat_b >> igw
    api_a >> Edge(style="dotted", label="egress") >> nat_a
    api_b >> Edge(style="dotted", label="egress") >> nat_b
    proxy >> Edge(style="dotted") >> secrets
    db_a >> Edge(style="dotted") >> backup
    gh >> gha >> Edge(label="deploy") >> cdn
