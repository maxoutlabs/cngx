# AWS CDK app for the cngx public tracker submit API

HTTP APIs do not support regional WAF association. This stack uses API Gateway HTTP API behind CloudFront with a CLOUDFRONT-scoped WAF web ACL (rate-based rule).

## Deploy

```bash
cd infra
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements.txt
export BUDGET_ALERT_EMAIL=you@example.com   # optional budget alerts
cdk deploy -a ".venv/Scripts/python app.py" --require-approval never
```

Copy `SubmitApiUrl` and `TrackerIndexUrl` into `tracker/public_endpoints.json`, then rebuild the tracker site.

Seed git-tracked community records after first deploy:

```bash
python scripts/seed_tracker_bucket.py <TrackerBucketName>
```
