import runner
# Two additional rotating rounds retain the original three and every observed outlier.
runner.timing(['dense-5000', 'empty-tail', 'output-heavy', 'merged'], repeats=2, start=3, warmup=False)
