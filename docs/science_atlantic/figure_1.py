import matplotlib.pyplot as plt
import timeit
from benchmark.convert import Converter

x = []
back = []
pd = []

evil = "(a + a)*"
re = Converter().math(evil)
i = 0

while True:
    word = "a"*i + "b"
    time = timeit.timeit(stmt=lambda: re.evalWordP_Backtrack(word), number=1)
    back.append(time)
    pd.append(timeit.timeit(stmt=lambda: re.evalWordP_PD(word), number=1))
    x.append(i)
    i += 1
    if time > 60:
        break

plt.title("Exponential Backtracking Demo")
plt.ylabel("membership time (s)")
plt.xlabel("word length (a^i b)")
plt.plot(x, back, linewidth=2, color="red", label="Backtracking")
plt.plot(x, pd, linewidth=5, color="blue", label="Partial Derivatives")
plt.legend(loc="best")
plt.show()
