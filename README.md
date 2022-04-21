# SMUHon-Practical-RE-Membership-Algs
_The Practical Efficiency of Regular Expression Membership Algorithms._ <br />
A Computing Science honours thesis project by Justin Gray at [Saint Mary's University](https://cs.smu.ca); supervised by [Dr. Konstantinidis](https://cs.smu.ca/~stavros).

## Thesis
The submitted thesis is available at the Saint Mary's Library, or in `docs/thesis.pdf`. This paper will provide background knowledge and context for the code in this repository.

## Installation
- NodeJS >14 (`$ node -v`) and a corresponding npm (`$ npm -v`) installation
- Python 2.7 (`$ python2 --version`) and a corresponding pip (`$ pip --version`) installation
- Make installation (`$ make -v`)

```bash
$ git clone https://github.com/just1ngray/SMUHon-Practical-RE-Membership-Algs.git
$ cd SMUHon-Practical-RE-Membership-Algs
$ make init
```

## Usage
1. Install using above instructions
2. `$ make test` to ensure everything is working (if it fails, then run it again: there are a couple of random tests that measure imperfect distributions)
3. `$ make sample` to generate the practical sample of regular expressions (the random sample has to be generated manually by starting a Python session)
4. `$ make bench` to benchmark the performance of the algorithms
5. `$ make sizes` to build the constructions and analyze the sizes

Some of the make scripts will execute Python code asking for runtime input. It should be reasonably straightforward to understand what each prompt means. If you are unsure, you can always check the source code.

Additionally, it is possible to skip the computationally expensive tasks by directly downloading the database(s) from a [GitHub release](https://github.com/just1ngray/SMUHon-Practical-RE-Membership-Algs/releases). Please download the most recent release of the databases, and follow the instructions on that page for more information.

## Project Structure
File/Folder | Description
----------- | -----------
`README.md` | This file!
`requirements.txt` | Python requirements for this project to work
`package.json` | To handle the node file `benchmark/parse.js`
`Makefile` | To save scripts used to execute the main features
`example_code_file.txt` | A snapshot of `benchmark/reex_ext.py` which is used to consistently generate input words in `benchmark/benchmark.py::Benchmarker#generateWords`. This file is considered a "typical" source file without empty lines
`.gitignore` | The files and folders that should not be committed here
`tests/` | Unit testing on some aspects of the code to improve confidence of correctness. However, poor overall coverage of the project
`FAdo_v1.3.5.1 (used for inspection only)/` | A snapshot of the FAdo version that has been extended. Note that nothing in this directory is imported, and a [pip installation of FAdo](https://pypi.org/project/fado/) is required
`docs/re_anchor_test.ipynb` | Demonstrate the behaviour of anchors in Python's `re` module
`docs/chars.txt` | A list of UTF-8 characters
`docs/science_atlantic/` | Science Atlantic Mathematics, Statistics, and Computer Science (MSCS) Conference (Oct. 2021) presentation of this research
`docs/thesis.pdf` | The final thesis; also available at SMU Library
`docs/thesis/` | The LaTeX source that generated the PDF, and the defence presentation

### Partial derivative membership story
Partial derivatives is a method to evaluate word membership for regular expressions. Read about them in the thesis for background knowledge and further explaination. But essentially, we expect there to be a partial derivative algorithm that can solve membership for one word faster than a we can construct a partial derivative NFA and then solve membership on the NFA using configurations. Preliminary results were showing partial derivatives to be really slow, but why?

The first deep-dive was saved in two files: `docs/pdOptimizations.py` and `docs/pd_results_saved.rtf`. It was here that we wrote the `benchmark/reex_ext.py::uregexp#evalWordP_PD` implementation of the partial derivative algorithm. We succeeded: word membership using `evalWordP_PD` was faster than the available `nfaPD` and `nfaPDO` constructions plus NFA membership.

However, when the `nfaPDDAG` algorithm became available, it was once again obvious there was serious room for improvement in the partial derivative algorithm. It was several months before a solution was found in the `docs/pd_algorithms.ipynb` file. The `benchmark/reex_ext.py::uregexp#evalWordP_PDO` method uses string identification in the `benchmark/reex_ext.py::uregexp` partial derivative function. `evalWordP_PDO` is faster than `nfaPDRPN`+NFA membership since it is built on the same technology, and sometimes it is even faster than `nfaPDDAG`+NFA membership.

There should be an algorithm which does a subset of the work from the `nfaPDDAG` construction, which can solve membership of one word faster than `nfaPDDAG`+NFA membership. No such algorithm is known at this time. Furthermore, partial derivative algorithms across the board could be improved using right concatenation recursion instead of left. This is explored in more detail in the thesis.

### `benchmark/` (main contributions)
- **re.lark** - The grammar used to parse a string into this project using `convert.py::Converter`
- **parse.js** - Parse a programmer's regular expression into a JSON object, then output in `re.lark` syntax
- **convert.py** - Convert mathematical and programmer's regular expressions into Python class objects
- **errors.py** - Errors passed around the project
- **fa_ext.py** - Extensions to FAdo's `fa::NFA`: the InvariantNFA with atomic class transitions instead of characters
- **reex_ext.py** - Extensions to FAdo's `reex`: corresponding classes
- **pddag.py** - The `nfaPDDAG` NFA construction algorithm which was not available in FAdo v1.3.5.1
- **sample.py** - Take a sample of practical regular expressions using [grep.app](https://grep.app) and GitHub. Or `RandomSampler` which generates random regular expressions
- **benchmark.py** - Run the benchmarks on the sample of regular expressions
- **nfa_sizes.py** - Analyze the size of the NFAs from the sample of regular expressions (larger NFAs tend to be slower to decide membership)
- **util.py** - Some utility functions (especially `DBWrapper`)