import sys
from fit_analyzer import FitAnalyzer

def main():
    analyzer = FitAnalyzer()
    return analyzer.run()

if __name__ == "__main__":
    sys.exit(main())