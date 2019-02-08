egg:
	python setup.py bdist_egg

PY_FILES=`find . -name '*.py' -not -path "*./build*" -not -path "./setup.py"`
pep8:
	pep8 --show-source --max-line-length=80 $(PY_FILES)

install-hook:
	cp pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
