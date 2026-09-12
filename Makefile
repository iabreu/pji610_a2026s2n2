SCOPE ?= ivanabreuelementardis-projects

.PHONY: help install check hooks ship dev-backend dev-frontend deploy deploy-backend deploy-frontend

help:
	@echo "install          instala dependencias do backend e do frontend"
	@echo "check            verifica tipos do frontend"
	@echo "hooks            ativa o hook de deploy automatico no git push"
	@echo "dev-backend      sobe a API em http://localhost:8000"
	@echo "dev-frontend     sobe o dashboard em http://localhost:3000"
	@echo "ship             faz push e depois publica em producao"
	@echo "deploy           publica backend e frontend em producao"
	@echo "deploy-backend   publica so o backend"
	@echo "deploy-frontend  publica so o frontend"

hooks:
	git config core.hooksPath .githooks

ship:
	git push origin main
	$(MAKE) deploy

install:
	cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	cd frontend && npm install

check:
	cd frontend && npx tsc --noEmit

dev-backend:
	cd backend && venv/bin/uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

deploy: deploy-backend deploy-frontend

deploy-backend:
	cd backend && vercel deploy --prod --yes --scope $(SCOPE)

deploy-frontend:
	cd frontend && vercel deploy --prod --yes --scope $(SCOPE)
