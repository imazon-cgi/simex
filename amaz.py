##Criado para tratar os dados previamente 
import pandas as pd 
import geopandas as gpd
import plotly.express as px 
import numpy as np 
import mapclassify	


gdf_mun = gpd.read_file(r"F:\VSCode\01 - CONSULTORIA\Ana\Asset\Mun_Amazonia_Legal_2022.shp")
gdf_mun.drop(columns=['CD_UF','AREA_INT','AREA_TOT','PORC_INT','NM_REGIAO'], inplace=True)

# Define a tolerância para a simplificação (ajuste o valor conforme necessário)
tolerancia = 0.01  # Unidade é geralmente em graus, ajuste conforme a precisão desejada

gdf_mun['geometry'] = gdf_mun['geometry'].simplify(tolerance=tolerancia, preserve_topology=True)

gdf_mun = gdf_mun.to_crs(epsg=4674)

output_path_geo = 'datasets/geojson/'
gdf_mun.to_file(f'{output_path_geo}limite_municipios_amz_legal.geojson')



# import geopandas as gpd


# def load_geojson(url):
#     try:
#         return gpd.read_file(url)
#     except Exception as e:
#         print(f"Erro ao carregar {url}: {e}")
#         return None

# # Carregar GeoJSON
# roi = load_geojson('https://github.com/ScriptsRemote/Amazon/raw/main/geojson/AMZ_municipios.geojson')
# roi

# ##Geoejson simplificado 
# gdf_edit = roi.drop(columns=['UF','AREA_KM2'])
# gdf_edit

# # Define a tolerância para a simplificação (ajuste o valor conforme necessário)
# tolerancia = 0.01  # Unidade é geralmente em graus, ajuste conforme a precisão desejada
 
# # Aplica a simplificação mantendo a topologia
# gdf_edit['geometry'] = gdf_edit['geometry'].simplify(tolerance=tolerancia, preserve_topology=True)

# output_path_geo = 'datasets/geojson/'
# gdf_edit.to_file(f'{output_path_geo}limite_municipios_amz_legal.geojson')