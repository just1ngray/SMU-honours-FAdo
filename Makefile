init:
	pip install -r requirements.txt

test:
	clear
	@echo "\n\n\n\n\n\n\n\n\n\n"
	@date

	@# python2 -m tests.test_convert
	@# python2 -m tests.test_reex_ext
	@# python2 -m tests.test_fa_ext

	python2 -m unittest discover tests

	@make clean

clean:
	find . -name '*.pyc' -delete