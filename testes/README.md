# Testes dos critérios de alerta

Roda quatro cenários (operação normal, picos isolados, variação brusca e deriva lenta) no banco do projeto e compara o limiar fixo com o limiar dinâmico.

```bash
pip install -r requirements.txt
export DATABASE_URL='postgresql://...'   # Supabase > Project Settings > Database > Session pooler
python3 executar_cenarios.py --remover-testes --api-url https://pji610-backend.vercel.app
```

- Cria dispositivos `TESTE-*` e insere 150 leituras por cenário (semente 42).
- `--remover-testes` apaga os `TESTE-*` de uma execução anterior antes de rodar de novo.
- Os resultados ficam em `../resultados/` (`results.json` e `fig_cenarios.png`).
- Para limpar no fim: `delete from pji610.dispositivos where nome like 'TESTE-%';`

A string de conexão nunca deve ser commitada.
