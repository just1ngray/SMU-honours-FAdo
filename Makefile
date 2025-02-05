init:
	@make break
	@echo "\nEXPECTING python2.7 and its corresponding pip installation"
	pip install -r requirements.txt
	@echo "\nEXPECTING node>14 and its corresponding npm installation"
	npm install

sizes:
	@make break
	python2 benchmark/nfa_sizes.py
	@make clean

bench:
	@make break
	@echo Run in privileged mode for priority scheduling
	nice -n -20 python2 benchmark/benchmark.py
	@make clean

sample:
	@make break
	python2 benchmark/sample.py
	@make clean

test:
	@make break

	@# python2 -m tests.test_util
	@# python2 -m tests.test_convert
	@# python2 -m tests.test_sample
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