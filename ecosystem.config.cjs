module.exports = {
  apps: [
    {
      name: "q3-web",
      cwd: "./apps/web",
      script: "pnpm",
      args: "dev",
      env: {
        PORT: "3000"
      }
    },
    {
      name: "q3-api",
      cwd: "./apps/api",
      script: "pnpm",
      args: "start",
      env: {
        PORT: "4000"
      }
    },
    {
      name: "q3-quant-engine",
      cwd: "./services/quant-engine",
      script: ".venv/bin/python",
      args: "-m q3_quant_engine",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "q3-quant-worker",
      cwd: "./services/quant-engine",
      script: ".venv/bin/celery",
      args: "-A q3_quant_engine.celery_app worker -Q strategy --loglevel=info",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "q3-market-ingestion",
      cwd: "./services/market-ingestion",
      script: ".venv/bin/python",
      args: "-m q3_market_ingestion",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
