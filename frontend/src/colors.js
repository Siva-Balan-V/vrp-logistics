export const ROUTE_COLORS = [
  '#f5a623','#3ecf8e','#4b9eff','#f2614a','#c084fc',
  '#fb7185','#34d399','#60a5fa','#fbbf24','#a78bfa',
  '#2dd4bf','#f87171','#818cf8','#4ade80','#e879f9',
  '#facc15','#38bdf8','#fb923c','#a3e635','#f472b6',
  '#22d3ee','#fd8a5e','#86efac','#c4b5fd','#fde68a',
  '#67e8f9','#fca5a5','#6ee7b7','#93c5fd','#d8b4fe',
]
export function routeColor(i){ return ROUTE_COLORS[i % ROUTE_COLORS.length] }
export function hexToRgba(hex,alpha=1){
  const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16)
  return `rgba(${r},${g},${b},${alpha})`
}
