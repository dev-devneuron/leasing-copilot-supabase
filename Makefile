SHELL := /bin/bash

.PHONY: init run test format lint clean

init:
	poetry install

format:
	poetry run black .




