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
      args: "-A q3_quant_engine.celery_app worker -Q strategy,backtest --loglevel=info",
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
    },
    {
      name: "q3-fundamentals-engine",
      cwd: "./services/fundamentals-engine",
      script: ".venv/bin/python",
      args: "-m q3_fundamentals_engine",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "q3-fundamentals-worker",
      cwd: "./services/fundamentals-engine",
      script: ".venv/bin/celery",
      args: "-A q3_fundamentals_engine.celery_app worker -Q fundamentals --loglevel=info",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "q3-ai-assistant",
      cwd: "./services/ai-assistant",
      script: ".venv/bin/python",
      args: "-m q3_ai_assistant",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "q3-ai-worker",
      cwd: "./services/ai-assistant",
      script: ".venv/bin/celery",
      args: "-A q3_ai_assistant.celery_app worker -Q ai-ranking,ai-backtest --loglevel=info",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "q3-ai-beat",
      cwd: "./services/ai-assistant",
      script: ".venv/bin/celery",
      args: "-A q3_ai_assistant.celery_app beat --loglevel=info",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
