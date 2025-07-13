# E2E Test Configuration

## Requirements

The end-to-end tests require additional dependencies:

```bash
pip install pytest pytest-asyncio playwright aiohttp
playwright install chromium
```

## Running E2E Tests

1. Start the WakeDock API server:
```bash
python manage.py dev
```

2. Start the dashboard (in another terminal):
```bash
cd dashboard
npm run dev
```

3. Run the tests:
```bash
pytest tests/e2e/ -v
```

## Test Scenarios

The e2e tests cover:
- Dashboard loading and navigation
- Service management interface
- Responsive design
- API connectivity
- Performance benchmarks
- Complete user workflows

## Configuration

E2E tests automatically detect if services are running:
- API Server: http://localhost:8000
- Dashboard: http://localhost:3000

If services are not running, tests will be skipped with appropriate messages.

## Browser Configuration

Tests run in headless Chromium by default. To run with visible browser:
```bash
pytest tests/e2e/ -v --headed
```

## Debugging

For debugging failed tests, use:
```bash
pytest tests/e2e/ -v -s --tb=long
```

Add screenshots on failure:
```bash
pytest tests/e2e/ -v --screenshot=on
```
