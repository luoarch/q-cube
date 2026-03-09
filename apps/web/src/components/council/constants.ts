import type { AgentId, AgentVerdict, ChatMode } from '@q3/shared-contracts';

export const VERDICT_COLORS: Record<AgentVerdict, string> = {
  buy: '#22c55e',
  watch: '#fbbf24',
  avoid: '#ef4444',
  insufficient_data: '#94a3b8',
};

export const VERDICT_LABELS: Record<AgentVerdict, string> = {
  buy: 'Comprar',
  watch: 'Observar',
  avoid: 'Evitar',
  insufficient_data: 'Dados Insuficientes',
};

export const AGENT_LABELS: Record<AgentId, string> = {
  barsi: 'Barsi-inspired',
  graham: 'Graham-inspired',
  greenblatt: 'Greenblatt-inspired',
  buffett: 'Buffett-inspired',
  moderator: 'Moderador Q\u00B3',
};

export const MODE_LABELS: Record<ChatMode, string> = {
  free_chat: 'Chat Livre',
  agent_solo: 'Agente Solo',
  roundtable: 'Mesa Redonda',
  debate: 'Debate',
  comparison: 'Comparacao',
};

export const DISCLAIMER =
  'Este conteudo e meramente educacional e analitico, nao constituindo recomendacao de investimento personalizada.';
