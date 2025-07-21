#!/usr/bin/env python3
"""
Brand Kit & Style Recipe Test Runner

This script runs all tests for the brand kit and style recipe implementation.
It provides comprehensive validation of the new features and generates a
detailed test report.

Usage:
    python run_brand_kit_tests.py [options]

Options:
    --verbose       Show detailed test output
    --coverage      Generate coverage report
    --integration   Run integration tests only
    --unit          Run unit tests only
    --e2e           Run end-to-end tests only
    --report        Generate HTML test report
"""

import os
import sys
import subprocess
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add churns to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test modules to run
TEST_MODULES = {
    'unit': [
        'test_brand_kit_integration.py',
        'test_style_adaptation_integration.py',
        'test_brand_presets_api.py',
        'test_pipeline_preset_integration.py'
    ],
    'integration': [
        'test_brand_kit_integration.py',
        'test_style_adaptation_integration.py',
        'test_pipeline_preset_integration.py'
    ],
    'e2e': [
        'test_brand_presets_e2e.py',
        'test_brand_kit_e2e_workflows.py'
    ]
}

class BrandKitTestRunner:
    """Test runner for brand kit and style recipe tests."""
    
    def __init__(self, verbose=False, coverage=False):
        self.verbose = verbose
        self.coverage = coverage
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'execution_time': 0,
            'test_details': []
        }
    
    def run_tests(self, test_type='all'):
        """Run the specified test type."""
        print(f"🧪 Running Brand Kit & Style Recipe Tests ({test_type})")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Determine which tests to run
        if test_type == 'all':
            test_files = []
            for category in TEST_MODULES.values():
                test_files.extend(category)
            test_files = list(set(test_files))  # Remove duplicates
        else:
            test_files = TEST_MODULES.get(test_type, [])
        
        if not test_files:
            print(f"❌ No tests found for type: {test_type}")
            return False
        
        # Run each test file
        for test_file in test_files:
            self._run_test_file(test_file)
        
        # Calculate execution time
        end_time = datetime.now()
        self.test_results['execution_time'] = (end_time - start_time).total_seconds()
        
        # Print summary
        self._print_summary()
        
        return self.test_results['failed_tests'] == 0
    
    def _run_test_file(self, test_file):
        """Run a single test file."""
        print(f"\n📋 Running {test_file}...")
        
        # Check if test file exists
        test_path = os.path.join(os.path.dirname(__file__), test_file)
        if not os.path.exists(test_path):
            print(f"⚠️  Test file not found: {test_file}")
            self.test_results['skipped_tests'] += 1
            return
        
        # Build pytest command
        cmd = ['python', '-m', 'pytest', test_path, '-v']
        
        if self.coverage:
            cmd.extend(['--cov=churns', '--cov-report=html'])
        
        if not self.verbose:
            cmd.append('-q')
        
        try:
            # Run the test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(__file__)
            )
            
            # Parse results
            output_lines = result.stdout.split('\n')
            passed = 0
            failed = 0
            skipped = 0
            
            for line in output_lines:
                if 'passed' in line and 'failed' in line:
                    # Parse pytest summary line
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'passed':
                            passed = int(parts[i-1])
                        elif part == 'failed':
                            failed = int(parts[i-1])
                        elif part == 'skipped':
                            skipped = int(parts[i-1])
            
            # Update results
            self.test_results['total_tests'] += passed + failed + skipped
            self.test_results['passed_tests'] += passed
            self.test_results['failed_tests'] += failed
            self.test_results['skipped_tests'] += skipped
            
            # Store detailed results
            self.test_results['test_details'].append({
                'file': test_file,
                'passed': passed,
                'failed': failed,
                'skipped': skipped,
                'status': 'PASSED' if failed == 0 else 'FAILED',
                'output': result.stdout if self.verbose else None,
                'error': result.stderr if result.stderr else None
            })
            
            # Print results
            if failed == 0:
                print(f"   ✅ {passed} tests passed")
            else:
                print(f"   ❌ {failed} tests failed, {passed} passed")
                if result.stderr:
                    print(f"   Error: {result.stderr}")
            
        except subprocess.CalledProcessError as e:
            print(f"   💥 Test execution failed: {e}")
            self.test_results['failed_tests'] += 1
            self.test_results['test_details'].append({
                'file': test_file,
                'passed': 0,
                'failed': 1,
                'skipped': 0,
                'status': 'ERROR',
                'output': None,
                'error': str(e)
            })
    
    def _print_summary(self):
        """Print test execution summary."""
        print("\n" + "=" * 60)
        print("📊 TEST EXECUTION SUMMARY")
        print("=" * 60)
        
        total = self.test_results['total_tests']
        passed = self.test_results['passed_tests']
        failed = self.test_results['failed_tests']
        skipped = self.test_results['skipped_tests']
        
        print(f"📋 Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Skipped: {skipped}")
        print(f"⏱️  Execution Time: {self.test_results['execution_time']:.2f} seconds")
        
        if total > 0:
            success_rate = (passed / total) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        print("\n📋 Test File Results:")
        for detail in self.test_results['test_details']:
            status_icon = "✅" if detail['status'] == 'PASSED' else "❌"
            print(f"   {status_icon} {detail['file']}: {detail['passed']} passed, {detail['failed']} failed, {detail['skipped']} skipped")
        
        if failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
            print("✅ Brand Kit & Style Recipe implementation is working correctly")
        else:
            print(f"\n⚠️  {failed} TESTS FAILED")
            print("🔍 Review the error messages above for details")
        
        print("=" * 60)
    
    def generate_report(self, output_file='test_report.html'):
        """Generate an HTML test report."""
        print(f"\n📄 Generating test report: {output_file}")
        
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Brand Kit & Style Recipe Test Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .summary { background: #f5f5f5; padding: 20px; margin: 20px 0; }
                .passed { color: #28a745; }
                .failed { color: #dc3545; }
                .skipped { color: #ffc107; }
                .test-file { margin: 10px 0; padding: 10px; border: 1px solid #ddd; }
                .test-file.passed { border-left: 4px solid #28a745; }
                .test-file.failed { border-left: 4px solid #dc3545; }
                .test-file.error { border-left: 4px solid #dc3545; background: #f8d7da; }
                pre { background: #f8f9fa; padding: 10px; overflow-x: auto; }
            </style>
        </head>
        <body>
            <h1>Brand Kit & Style Recipe Test Report</h1>
            <p>Generated: {timestamp}</p>
            
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Total Tests:</strong> {total_tests}</p>
                <p><strong class="passed">Passed:</strong> {passed_tests}</p>
                <p><strong class="failed">Failed:</strong> {failed_tests}</p>
                <p><strong class="skipped">Skipped:</strong> {skipped_tests}</p>
                <p><strong>Execution Time:</strong> {execution_time:.2f} seconds</p>
                <p><strong>Success Rate:</strong> {success_rate:.1f}%</p>
            </div>
            
            <h2>Test Results</h2>
            {test_details}
        </body>
        </html>
        """
        
        # Generate test details HTML
        test_details_html = ""
        for detail in self.test_results['test_details']:
            status_class = detail['status'].lower()
            test_details_html += f"""
            <div class="test-file {status_class}">
                <h3>{detail['file']} - {detail['status']}</h3>
                <p>Passed: {detail['passed']}, Failed: {detail['failed']}, Skipped: {detail['skipped']}</p>
                {f'<pre>{detail["error"]}</pre>' if detail.get('error') else ''}
            </div>
            """
        
        # Calculate success rate
        total = self.test_results['total_tests']
        passed = self.test_results['passed_tests']
        success_rate = (passed / total * 100) if total > 0 else 0
        
        # Generate final HTML
        html_content = html_template.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_tests=total,
            passed_tests=passed,
            failed_tests=self.test_results['failed_tests'],
            skipped_tests=self.test_results['skipped_tests'],
            execution_time=self.test_results['execution_time'],
            success_rate=success_rate,
            test_details=test_details_html
        )
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"✅ Test report generated: {output_file}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run Brand Kit & Style Recipe tests')
    parser.add_argument('--verbose', action='store_true', help='Show detailed test output')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--e2e', action='store_true', help='Run end-to-end tests only')
    parser.add_argument('--report', action='store_true', help='Generate HTML test report')
    
    args = parser.parse_args()
    
    # Determine test type
    test_type = 'all'
    if args.unit:
        test_type = 'unit'
    elif args.integration:
        test_type = 'integration'
    elif args.e2e:
        test_type = 'e2e'
    
    # Create test runner
    runner = BrandKitTestRunner(verbose=args.verbose, coverage=args.coverage)
    
    # Run tests
    success = runner.run_tests(test_type)
    
    # Generate report if requested
    if args.report:
        runner.generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main() 