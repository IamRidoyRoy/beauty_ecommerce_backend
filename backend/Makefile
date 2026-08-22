install:
	python -m pip install -r requirements.txt
migrations:
	python manage.py makemigrations
	python manage.py migrate
seed:
	python manage.py seed_full_demo
check:
	python manage.py check
	python manage.py test
schema:
	python manage.py spectacular --file schema.yml --validate
run:
	python manage.py runserver
