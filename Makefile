SHELL := /usr/bin/env bash

.PHONY: help check repos setup papers data-smoke data-benchmark train-smoke

help:
	@echo "make check           Validate host tools and GPU visibility"
	@echo "make repos           Fetch the pinned runtime repository"
	@echo "make setup           Build the pinned Pixi runtime and validate CUDA"
	@echo "make papers          Download the seven core papers"
	@echo "make data-smoke      Download Nerfstudio poster smoke-test data"
	@echo "make data-benchmark  Download/extract the chosen Mip-NeRF 360 scenes"
	@echo "make train-smoke     Train Nerfacto on poster after setup"

check:
	bash scripts/check_environment.sh

repos:
	bash scripts/download_repos.sh runtime

setup:
	bash scripts/setup_runtime.sh

papers:
	bash scripts/download_papers.sh

data-smoke:
	bash scripts/download_datasets.sh smoke

data-benchmark:
	bash scripts/download_datasets.sh benchmark

train-smoke:
	bash scripts/train.sh nerfacto poster
