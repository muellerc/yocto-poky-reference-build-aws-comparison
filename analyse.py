import os
import re

pattern = re.compile(r"^real\t(.*)m(.*)s$")
results = []
min = 0
max = 0
total = 0

for subdir, dirs, files in os.walk("tmp"):
    for file in files:
        fqn = os.path.join(subdir, file)
        # print(fqn)

        if fqn.endswith(".txt"):
            f = open(fqn, "r")
            for line in f:
                # print(line)
                match = pattern.match(line)

                if match:
                    # print(match.group())
                    # print(match.group(1))
                    # print(match.group(2))

                    benchmark_result = int(match.group(1)) * 60 + int(float(match.group(2)))
                    print(benchmark_result)
                    results.append(benchmark_result)
            f.close()

    for measurement in results:
        total = total + measurement

        if min == 0 or min > measurement:
            min = measurement

        if max == 0 or max < measurement:
            max = measurement

    avg = int(total / len(results))
    print(str(len(results)) + ' Instances')
    print('min: ' + str(int(min / 60)) + 'm ' + str(min - (int(min / 60) * 60)) + 's')
    print('max: ' + str(int(max / 60)) + 'm ' + str(max - (int(max / 60) * 60)) + 's')
    print('avg: ' + str(int(avg / 60)) + 'm ' + str(avg - (int(avg / 60) * 60)) + 's')
