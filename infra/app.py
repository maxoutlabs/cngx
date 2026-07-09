#!/usr/bin/env python3
import os

import aws_cdk as cdk

from tracker_submit.stack import TrackerSubmitStack

app = cdk.App()

TrackerSubmitStack(
    app,
    "CngxTrackerSubmitStack",
    budget_alert_email=os.environ.get("BUDGET_ALERT_EMAIL", ""),
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
