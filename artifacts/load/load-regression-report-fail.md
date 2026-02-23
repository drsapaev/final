# Load Test Regression Report

- Status: FAIL
- RPS: 10.00
- P95 latency: 900.00 ms
- Error rate: 0.2000
- Checks success: 0.5000

## Failures
- RPS below target: 10.00 < 25.00
- P95 latency above target: 900.00ms > 500.00ms
- Error rate above target: 0.2000 > 0.0100
- Checks success below target: 0.5000 < 0.9900
- RPS regression exceeded: 10.00 < 25.50 (baseline 30.00, drop limit 15.00%)
- P95 regression exceeded: 900.00ms > 540.00ms (baseline 450.00ms, increase limit 20.00%)
