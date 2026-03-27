# Migration Steps (on server)

## 1. Extract code
cd ~
tar xzf code.tar.gz -C personal-ai/

## 2. Setup Python venv
cd ~/personal-ai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

## 3. Configure .env
cp .env.template .env
# Edit .env — fill in actual API keys

## 4. Restore DB
gunzip -c gilbertus_db.sql.gz | sudo docker exec -i gilbertus-postgres psql -U gilbertus -d gilbertus

## 5. Re-index Qdrant
.venv/bin/python -m app.retrieval.index_chunks --batch-size 200 --limit 0

## 6. Install crontab
crontab crontab.txt

## 7. Start API
bash scripts/run_api.sh

## 8. Install nginx + certbot
sudo apt install -y nginx certbot python3-certbot-nginx
# Configure reverse proxy for :8000

## 9. Verify
curl http://localhost:8000/health
curl http://localhost:8000/status
