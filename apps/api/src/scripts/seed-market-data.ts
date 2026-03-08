/**
 * Seed script: Populates market data (prices, sectors) for development.
 *
 * This is the local alternative to enabling ENABLE_BRAPI=true.
 * It updates existing assets and financial_statements with realistic
 * sample prices, market caps, and sectors.
 *
 * Usage: npx tsx src/scripts/seed-market-data.ts
 */

import { eq, sql } from 'drizzle-orm';
import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';

import { assets, financialStatements, issuers } from '../db/schema.js';

const DATABASE_URL = process.env.DATABASE_URL ?? 'postgresql://127.0.0.1:5432/q3';

// Sample sector mapping for well-known Brazilian tickers
const SECTOR_MAP: Record<string, { sector: string; subSector: string }> = {
  PETR4: {
    sector: 'Petróleo, Gás e Biocombustíveis',
    subSector: 'Exploração, Refino e Distribuição',
  },
  PETR3: {
    sector: 'Petróleo, Gás e Biocombustíveis',
    subSector: 'Exploração, Refino e Distribuição',
  },
  VALE3: { sector: 'Materiais Básicos', subSector: 'Mineração' },
  WEGE3: { sector: 'Bens Industriais', subSector: 'Máquinas e Equipamentos' },
  ITUB4: { sector: 'Financeiro', subSector: 'Intermediários Financeiros' },
  ITUB3: { sector: 'Financeiro', subSector: 'Intermediários Financeiros' },
  BBDC4: { sector: 'Financeiro', subSector: 'Intermediários Financeiros' },
  BBDC3: { sector: 'Financeiro', subSector: 'Intermediários Financeiros' },
  BBAS3: { sector: 'Financeiro', subSector: 'Intermediários Financeiros' },
  ABEV3: { sector: 'Consumo não Cíclico', subSector: 'Bebidas' },
  B3SA3: { sector: 'Financeiro', subSector: 'Serviços Financeiros Diversos' },
  RENT3: { sector: 'Consumo Cíclico', subSector: 'Diversos' },
  SUZB3: { sector: 'Materiais Básicos', subSector: 'Madeira e Papel' },
  LREN3: { sector: 'Consumo Cíclico', subSector: 'Comércio' },
  HAPV3: { sector: 'Saúde', subSector: 'Serviços Médico-Hospitalares' },
  RAIL3: { sector: 'Bens Industriais', subSector: 'Transporte' },
  JBSS3: { sector: 'Consumo não Cíclico', subSector: 'Alimentos Processados' },
  GGBR4: { sector: 'Materiais Básicos', subSector: 'Siderurgia e Metalurgia' },
  CSNA3: { sector: 'Materiais Básicos', subSector: 'Siderurgia e Metalurgia' },
  VIVT3: { sector: 'Comunicações', subSector: 'Telecomunicações' },
  CMIG4: { sector: 'Utilidade Pública', subSector: 'Energia Elétrica' },
  ELET3: { sector: 'Utilidade Pública', subSector: 'Energia Elétrica' },
  ELET6: { sector: 'Utilidade Pública', subSector: 'Energia Elétrica' },
  EMBR3: { sector: 'Bens Industriais', subSector: 'Material de Transporte' },
  MGLU3: { sector: 'Consumo Cíclico', subSector: 'Comércio' },
  TOTS3: { sector: 'Tecnologia da Informação', subSector: 'Programas e Serviços' },
  RADL3: { sector: 'Saúde', subSector: 'Comércio e Distribuição' },
  EQTL3: { sector: 'Utilidade Pública', subSector: 'Energia Elétrica' },
  CPLE6: { sector: 'Utilidade Pública', subSector: 'Energia Elétrica' },
  SBSP3: { sector: 'Utilidade Pública', subSector: 'Água e Saneamento' },
};

// Sample prices for known tickers (approximate BRL values)
const PRICE_MAP: Record<string, { price: number; marketCap: number }> = {
  PETR4: { price: 38.5, marketCap: 500_000_000_000 },
  PETR3: { price: 42.1, marketCap: 500_000_000_000 },
  VALE3: { price: 62.3, marketCap: 270_000_000_000 },
  WEGE3: { price: 55.2, marketCap: 140_000_000_000 },
  ITUB4: { price: 33.8, marketCap: 320_000_000_000 },
  BBDC4: { price: 13.9, marketCap: 140_000_000_000 },
  BBAS3: { price: 28.5, marketCap: 160_000_000_000 },
  ABEV3: { price: 13.2, marketCap: 210_000_000_000 },
  B3SA3: { price: 11.5, marketCap: 65_000_000_000 },
  RENT3: { price: 42.8, marketCap: 45_000_000_000 },
  SUZB3: { price: 58.9, marketCap: 80_000_000_000 },
  LREN3: { price: 14.6, marketCap: 14_000_000_000 },
  HAPV3: { price: 3.8, marketCap: 28_000_000_000 },
  RAIL3: { price: 22.1, marketCap: 38_000_000_000 },
  JBSS3: { price: 36.4, marketCap: 82_000_000_000 },
  GGBR4: { price: 18.2, marketCap: 34_000_000_000 },
  CSNA3: { price: 11.3, marketCap: 15_000_000_000 },
  VIVT3: { price: 53.6, marketCap: 90_000_000_000 },
  CMIG4: { price: 12.8, marketCap: 36_000_000_000 },
  ELET3: { price: 44.5, marketCap: 85_000_000_000 },
  EMBR3: { price: 52.3, marketCap: 39_000_000_000 },
  MGLU3: { price: 8.2, marketCap: 5_500_000_000 },
  TOTS3: { price: 30.5, marketCap: 18_000_000_000 },
  RADL3: { price: 26.3, marketCap: 44_000_000_000 },
  EQTL3: { price: 32.1, marketCap: 36_000_000_000 },
};

// Default sector groups for tickers not in SECTOR_MAP
const DEFAULT_SECTORS = [
  { sector: 'Financeiro', subSector: 'Intermediários Financeiros' },
  { sector: 'Consumo Cíclico', subSector: 'Comércio' },
  { sector: 'Utilidade Pública', subSector: 'Energia Elétrica' },
  { sector: 'Bens Industriais', subSector: 'Máquinas e Equipamentos' },
  { sector: 'Materiais Básicos', subSector: 'Mineração' },
  { sector: 'Saúde', subSector: 'Serviços Médico-Hospitalares' },
  { sector: 'Tecnologia da Informação', subSector: 'Programas e Serviços' },
  { sector: 'Consumo não Cíclico', subSector: 'Alimentos Processados' },
  { sector: 'Comunicações', subSector: 'Telecomunicações' },
  { sector: 'Petróleo, Gás e Biocombustíveis', subSector: 'Exploração, Refino e Distribuição' },
];

function pseudoRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

async function main() {
  const pool = new Pool({ connectionString: DATABASE_URL });
  const db = drizzle(pool);

  console.log('Seeding market data...\n');

  // 1. Update asset sectors
  const allAssets = await db.select({ id: assets.id, ticker: assets.ticker }).from(assets);
  let sectorUpdated = 0;

  for (const asset of allAssets) {
    const sectorInfo = SECTOR_MAP[asset.ticker];
    if (sectorInfo) {
      await db
        .update(assets)
        .set({ sector: sectorInfo.sector, subSector: sectorInfo.subSector, updatedAt: new Date() })
        .where(eq(assets.id, asset.id));
      sectorUpdated++;
    } else {
      // Assign a deterministic sector based on ticker hash
      const hash = asset.ticker.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
      const defaultSector = DEFAULT_SECTORS[hash % DEFAULT_SECTORS.length]!;
      await db
        .update(assets)
        .set({
          sector: defaultSector.sector,
          subSector: defaultSector.subSector,
          updatedAt: new Date(),
        })
        .where(eq(assets.id, asset.id));
      sectorUpdated++;
    }
  }
  console.log(`Updated sectors for ${sectorUpdated} assets`);

  // 2. Update issuer sectors (global tables)
  const allIssuers = await db
    .select({ id: issuers.id, legalName: issuers.legalName, sector: issuers.sector })
    .from(issuers);
  let issuerSectorUpdated = 0;

  for (const issuer of allIssuers) {
    if (!issuer.sector) {
      const hash = issuer.legalName.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
      const defaultSector = DEFAULT_SECTORS[hash % DEFAULT_SECTORS.length];
      await db
        .update(issuers)
        .set({
          sector: defaultSector.sector,
          subsector: defaultSector.subSector,
          updatedAt: new Date(),
        })
        .where(eq(issuers.id, issuer.id));
      issuerSectorUpdated++;
    }
  }
  console.log(`Updated sectors for ${issuerSectorUpdated} issuers`);

  // 3. Update financial_statements with enterprise_value and market_cap
  const allFS = await db
    .select({
      id: financialStatements.id,
      assetId: financialStatements.assetId,
      ebit: financialStatements.ebit,
      netDebt: financialStatements.netDebt,
    })
    .from(financialStatements);

  // Build asset ticker map
  const assetTickerMap = new Map<string, string>();
  for (const a of allAssets) {
    assetTickerMap.set(a.id, a.ticker);
  }

  let fsUpdated = 0;
  for (const fs of allFS) {
    const ticker = assetTickerMap.get(fs.assetId);
    if (!ticker) continue;

    const priceInfo = PRICE_MAP[ticker];
    const marketCap = priceInfo
      ? priceInfo.marketCap
      : Math.round(
          pseudoRandom(ticker.charCodeAt(0) + ticker.charCodeAt(1)) * 50_000_000_000 +
            1_000_000_000,
        );

    const netDebt = fs.netDebt ? Number(fs.netDebt) : 0;
    const enterpriseValue = marketCap + netDebt;

    await db
      .update(financialStatements)
      .set({
        marketCap: String(marketCap),
        enterpriseValue: String(enterpriseValue),
        updatedAt: new Date(),
      })
      .where(eq(financialStatements.id, fs.id));
    fsUpdated++;
  }
  console.log(`Updated market_cap/enterprise_value for ${fsUpdated} financial statements`);

  // Summary
  const totalAssets = allAssets.length;
  const sectorCounts = new Map<string, number>();
  for (const a of allAssets) {
    const s = SECTOR_MAP[a.ticker]?.sector ?? 'Other';
    sectorCounts.set(s, (sectorCounts.get(s) ?? 0) + 1);
  }

  console.log(`\nSummary:`);
  console.log(`  ${totalAssets} assets with sectors`);
  console.log(`  ${issuerSectorUpdated} issuers with sectors`);
  console.log(`  ${fsUpdated} financial statements with market data`);
  console.log(`\nSector distribution (known tickers):`);
  for (const [sector, count] of Array.from(sectorCounts.entries()).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${sector}: ${count}`);
  }

  await pool.end();
  console.log('\nDone!');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
