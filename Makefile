.PHONY: all

clean:
	rm -r dist || true

dist: clean
	python setup.py sdist --format=gztar > /dev/null # silence the sdist output! Too noisy!
	python setup.py bdist_wheel
	ls -l dist

release: dist
	twine upload -s dist/*