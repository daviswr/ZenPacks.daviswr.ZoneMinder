PY_FILES=`find . -name '*.py' -not -path "*./build*" -not -path "./setup.py"`
ZP_DIR:=$(shell pwd)
ZP_NAME:=$(shell basename $(ZP_DIR))
ZP_PATH:=$(shell echo $(ZP_NAME) | sed 's!\.!/!g')

.PHONY: egg
egg:
	python setup.py bdist_egg

.PHONY: pep8
pep8:
	pep8 --show-source --max-line-length=80 $(PY_FILES)

.PHONY: install-hook
install-hook:
	cp pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

.PHONY: restart
restart:
	zopectl restart
	zenhub restart
	zenpython restart

.PHONY: lint
lint:
	zenpacklib --lint $(ZP_DIR)/$(ZP_PATH)/zenpack.yaml

.PHONY: link-install-pack
link-install-pack:
	zenpack --link --install $(ZP_DIR)

.PHONY: link-install
link-install: link-install-pack restart

.PHONY: remove-pack
remove-pack:
	zenpack --remove $(ZP_NAME)

.PHONY: remove
remove: remove-pack restart
