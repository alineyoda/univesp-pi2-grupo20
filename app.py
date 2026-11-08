"""Ponto de entrada da aplicação.

Local (desenvolvimento):   python app.py      ou   flask run
Produção (Render):         gunicorn app:app
"""
from salao import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
