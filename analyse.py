import numpy as np

import os
import re

pattern = re.compile(r"^real\t(.*)m(.*)s$")
results = []

for subdir, dirs, files in os.walk("tmp"):
    for file in files:
        fqn = os.path.join(subdir, file)

        if fqn.endswith(".txt"):
            f = open(fqn, "r")

            for line in f:
                match = pattern.match(line)

                if match:
                    benchmark_result = int(match.group(1)) * 60 + int(float(match.group(2)))
                    results.append(benchmark_result)
            f.close()

    p0 = np.percentile(results, 0)
    p50 = np.percentile(results, 50)
    p75 = np.percentile(results, 75)
    p90 = np.percentile(results, 90)
    p98 = np.percentile(results, 98)
    p100 = np.percentile(results, 100)

    print('P0: ' + str(int(p0 / 60)) + 'm ' + str(p0 - (int(p0 / 60) * 60)) + 's')
    print('P50: ' + str(int(p50 / 60)) + 'm ' + str(p50 - (int(p50 / 60) * 60)) + 's')
    print('P75: ' + str(int(p75 / 60)) + 'm ' + str(p75 - (int(p75 / 60) * 60)) + 's')
    print('P90: ' + str(int(p90 / 60)) + 'm ' + str(p90 - (int(p90 / 60) * 60)) + 's')
    print('P98: ' + str(int(p98 / 60)) + 'm ' + str(p98 - (int(p98 / 60) * 60)) + 's')
    print('P100: ' + str(int(p100 / 60)) + 'm ' + str(p100 - (int(p100 / 60) * 60)) + 's')
