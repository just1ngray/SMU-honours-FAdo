init:
	@make break
	@echo "\nEXPECTING python2.7 and its corresponding pip installation"
	pip install -r requirements.txt
	@echo "\nEXPECTING node>14 and its corresponding npm installation"
	npm install

sample:
	@make break
	python2 -m benchmark.sample
	@make clean

test:
	@make break

	@# python2 -m tests.test_convert
	@# python2 -m tests.test_reex_ext
	@# python2 -m tests.test_fa_ext
	python2 -m unittest discover tests

	@make clean

clean:
	@find . -name '*.pyc' -delete

break:
	clear
	@echo "\n\n\n\n\n\n\n\n\n\n"
	@date