THIS_FILE := $(lastword $(MAKEFILE_LIST))
.PHONY: make

make:
	python3 main.py