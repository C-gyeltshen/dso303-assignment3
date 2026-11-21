"""Assignment 3 revised architecture. Regenerate architecture/architecture.png:
    pip install diagrams && python architecture/diagram.py
Labels: [SPOF-R] = single point of failure removed, [SPOF-A] = accepted (see architecture/README.md), [A3] = changed in Assignment 3.
"""
from diagrams import Cluster, Diagram, Edge
from diagrams.aws.network import Route53, CloudFront, APIGateway, Endpoint, Privatelink
from diagrams.aws.security import WAF, Cognito, SecretsManager, KMS
from diagrams.aws.storage import S3, Backup
from diagrams.aws.compute import Lambda
from diagrams.aws.database import RDSPostgresqlInstance, RDS
from diagrams.aws.integration import SQS
from diagrams.aws.engagement import SES
from diagrams.aws.management import Cloudwatch, CloudwatchAlarm, Cloudtrail
from diagrams.onprem.client import Users
from diagrams.onprem.ci import GithubActions

graph = {"fontsize": "22", "pad": "0.5", "nodesep": "1.0", "ranksep": "0.85", "splines": "spline",
         "label": "[SPOF-R] = single point of failure removed   [SPOF-A] = accepted (see SPOF register)   [A3] = changed since Assignment 2",
         "labelloc": "b"}
red = {"fontcolor": "firebrick"}

with Diagram("Exam platform – revised, cost-optimised (ap-southeast-1 Singapore, 2 AZs)",
             filename="architecture/architecture", show=False, direction="TB", graph_attr=graph, outformat="png"):
    users = Users("Students / tutors / admins\n(Bhutan, via CloudFront India edges)")

    with Cluster("Edge (global)"):
        dns = Route53("Route 53\n[SPOF-A: 100% SLA]")
        waf = WAF("WAF: managed rules +\nrate limit, campus IPs exempt [A3]")
        cdn = CloudFront("CloudFront\n/ -> SPA  /api -> API\n/submissions -> files (signed) [A3]")

    with Cluster("Regional managed services (multi-AZ by design)"):
        cognito = Cognito("Cognito (Essentials,\n8.4k MAU free)\n[SPOF-A: regional service]")
        api = APIGateway("HTTP API + JWT authorizer\nthrottle 1,000 rps")
        web = S3("S3 SPA bucket")
        uploads = S3("S3 uploads: IA 30 d ->\nDeep Archive 180 d [A3]\n-> delete 5 y")
        q = SQS("SQS: marking, uploads,\nnotify, email [A3] + DLQs")
        mailer = Lambda("mailer Lambda\n(outside VPC) [A3]")
        admin = Lambda("admin Lambda\n(outside VPC) [A3]")
        ses = SES("SES\n[SPOF-A: queued + DLQ]")

    with Cluster("VPC 10.0.0.0/16 – no NAT gateways, no internet route from private subnets [A3]"):
        s3ep = Endpoint("S3 gateway endpoint\n(free)")
        with Cluster("AZ-a"):
            with Cluster("Private app 10.0.10.0/24"):
                api_a = Lambda("API Lambda (alias live,\nprov. concurrency in exams)")
                wk_a = Lambda("marker / upload-\nprocessor / notifier")
                ep_a = Privatelink("SQS + Secrets\nendpoint ENIs")
            with Cluster("Private data 10.0.20.0/24"):
                db_a = RDSPostgresqlInstance("RDS PostgreSQL PRIMARY\nt4g.medium RI / t4g.large exams")
        with Cluster("AZ-b"):
            with Cluster("Private app 10.0.11.0/24"):
                api_b = Lambda("API Lambda")
                wk_b = Lambda("workers")
                ep_b = Privatelink("SQS + Secrets\nendpoint ENIs")
            with Cluster("Private data 10.0.21.0/24"):
                db_b = RDSPostgresqlInstance("RDS STANDBY\n[SPOF-R: sync replica]")
        proxy = RDS("RDS Proxy, IAM auth [A3]\n[SPOF-R: multi-AZ]")

    with Cluster("Security, ops, DR"):
        kms = KMS("KMS CMK\n[SPOF-A: 7-day deletion window]")
        secrets = SecretsManager("Secrets Manager\n(proxy only) [A3]")
        cw = Cloudwatch("CloudWatch: JSON WARN logs,\n30 d, IA class [A3]")
        alarm = CloudwatchAlarm("Alarms -> SNS\n(latency, throttles,\nDLQ, CPU credits)")
        trail = Cloudtrail("CloudTrail")
        backup = Backup("PITR 35 d (RPO 5 min)\n+ monthly 5 y")
        ci = GithubActions("GitHub Actions -> Terraform\nexam_mode toggle [A3]")

    users >> dns >> cdn
    waf - Edge(style="dashed") - cdn
    users >> Edge(label="sign-in") >> cognito
    cdn >> web
    cdn >> Edge(label="/api/*") >> api
    cdn >> Edge(label="/submissions/* (OAC)") >> uploads
    users >> Edge(label="presigned POST <= 50 MB", color="darkgreen") >> uploads
    api - Edge(style="dashed") - cognito
    api >> [api_a, api_b]
    api >> Edge(label="/api/admin/*") >> admin >> cognito
    [api_a, api_b, wk_a, wk_b] >> proxy >> db_a
    db_a - Edge(label="sync", style="dashed") - db_b
    [api_a, wk_a] >> ep_a >> q
    [api_b, wk_b] >> ep_b
    uploads >> Edge(label="ObjectCreated") >> q
    q >> [wk_a, wk_b]
    q >> mailer >> ses
    wk_a >> s3ep >> uploads
    proxy >> Edge(style="dotted") >> secrets
    db_a >> Edge(style="dotted") >> backup
    cw >> alarm
    ci >> Edge(style="dotted", label="deploy") >> cdn
