FROM python:3.11

# On se place dans le dossier /code
WORKDIR /code

# On installe les dépendances
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# On copie le reste du projet
COPY . .

# Hugging Face utilise le port 7860 par défaut
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:7860", "--timeout", "120", "--workers", "2"]
