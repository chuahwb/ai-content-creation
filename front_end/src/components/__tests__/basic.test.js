// Basic test to verify Jest configuration
describe('Basic Jest Test', () => {
  it('should pass a simple test', () => {
    expect(1 + 1).toBe(2);
  });

  it('should work with basic DOM', () => {
    const div = document.createElement('div');
    div.textContent = 'Hello World';
    
    expect(div.textContent).toBe('Hello World');
  });
}); 