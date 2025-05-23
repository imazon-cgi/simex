# app/__init__.py
from flask import Flask
from app.dashboards.simex_assentamentos import register_simex_assentamentos_dashboard
from app.dashboards.simex_imoveis_rurais import register_simex_imoveis_rurais_dashboard
from app.dashboards.simex_municipios import register_simex_municipios_dashboard
from app.dashboards.simex_terra_dest import register_simex_terra_dest_dashboard
from app.dashboards.simex_ti import register_simex_terras_indigenas_dashboard
from app.dashboards.simex_uc import register_simex_uc_dashboard

def create_app():
    server = Flask(__name__)
    register_simex_assentamentos_dashboard(server)  # rota /simex_assentamentos/
    register_simex_imoveis_rurais_dashboard(server) # rota /simex_imoveis_rurais/
    register_simex_municipios_dashboard(server)  # rota /simex_municipios/
    register_simex_terra_dest_dashboard(server)  # rota /simex_terra_dest/
    register_simex_terras_indigenas_dashboard(server) # rota /simex_ti/
    register_simex_uc_dashboard(server) # rota /simex_uc/
    
    return server 
