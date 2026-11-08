"""Instâncias compartilhadas das extensões do Flask.

Ficam em um módulo separado para evitar importações circulares:
os models importam `db` daqui, e a fábrica da aplicação o inicializa.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
