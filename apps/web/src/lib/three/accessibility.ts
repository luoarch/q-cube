export function announceSelection(ticker: string | null) {
  if (typeof document === 'undefined') return;
  const el = document.getElementById('scene-live-region');
  if (!el) return;
  el.textContent = ticker ? `Ativo selecionado: ${ticker}` : 'Seleção removida';
}
