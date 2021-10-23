# Evil expression and words from:
# https://algs4.cs.princeton.edu/54regexp/
import matplotlib.pyplot as plt
import re
import timeit

evilRE = re.compile("(a|aa)*b")
x = []
y = []
i = 0
while True:
    word = "a"*i + "c"
    time = timeit.timeit(lambda: evilRE.search(word), number=1)
    y.append(time)
    x.append(i)
    i += 1
    if time > 1 or i > 100:
        break

plt.title("Python Demo")
plt.ylabel("membership time (s)")
plt.xlabel("word length (a^i c)")
plt.plot(x, y, linewidth=2, color="red")
plt.show()
