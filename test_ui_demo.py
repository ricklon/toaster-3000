"""
Toaster 3000 UI Testing Demo
This script demonstrates how to test the Toaster 3000 UI using Playwright MCP.
"""
import os
import sys


def show_ui_testing_guide():
    """Display a comprehensive guide for testing the Toaster 3000 UI"""
    print("🍞 TOASTER 3000 UI TESTING GUIDE")
    print("=" * 60)
    print("""
Welcome to the Toaster 3000 UI Testing Guide!

This guide shows you how to test the Toaster 3000 user interface using
Playwright MCP integration available in Claude Code.

PREREQUISITES:
1. Ensure you have a valid HUGGINGFACE_API_KEY in your .env file
2. Make sure the Playwright MCP server is configured and working
3. Have the Toaster 3000 application ready to run

STEP 1: Start the Application
Run this command to start Toaster 3000:
    uv run python src/toaster_3000/toaster_3000.py

The app will start on http://127.0.0.1:7860 (or similar URL shown in output)

STEP 2: Test Scenarios to Run with Playwright MCP

🔍 Basic Page Load Test:
Ask Claude Code with Playwright MCP:
"Navigate to http://127.0.0.1:7860 and verify the Toaster 3000 page loads successfully."

Expected Result: Page loads with Toaster 3000 title and orange/yellow theme

🔍 UI Elements Verification:
Ask Claude Code:
"Check that the following elements are present on the Toaster 3000 page:
- Page title 'Toaster 3000' with bread emoji
- Introduction message section
- Text input field with placeholder text
- Send Message button
- Audio input components
- Model selection dropdown
- Intelligence level slider
- Conversation display area"

🔍 Text Interaction Test:
Ask Claude Code:
"Type 'What is the best bread for making toast?' in the text input field and click Send Message. Wait for the response and verify it appears in the conversation display."

Expected Result: Toaster responds with enthusiastic toast-related advice

🔍 Model Selection Test:
Ask Claude Code:
"Test the model selection dropdown by selecting a different model and clicking the 'Change Model' button. Verify a status message appears."

🔍 Intelligence Level Test:
Ask Claude Code:
"Move the intelligence level slider to a different value and click 'Set Toaster Intelligence'. Verify the status updates."

🔍 Chat Clear Test:
Ask Claude Code:
"After having a conversation, click the 'Clear Chat' button and verify the conversation resets to just the introduction message."

🔍 Responsive Design Test:
Ask Claude Code:
"Set the browser viewport to mobile size (375x667) and verify the Toaster 3000 interface adapts properly with elements stacking vertically."

🔍 Theme and Styling Test:
Ask Claude Code:
"Verify the Toaster 3000 page has the correct styling:
- Orange/yellow gradient background
- Toaster-themed colors
- Proper button styling with orange background
- Chat messages with distinct user/bot styling"

🔍 Audio Components Test:
Ask Claude Code:
"Verify that audio input/output components are visible:
- Push-to-talk microphone button
- Audio output players
- Continuous listening toggle"

🔍 Error Handling Test:
Ask Claude Code:
"Test error scenarios by disconnecting internet or using invalid input, and verify appropriate error messages appear."

STEP 3: Advanced Testing Scenarios

🧪 Full Conversation Flow:
Test a complete conversation about toasting, verifying:
- Messages appear in correct order
- Toaster personality comes through
- Audio responses work (if testing audio)
- Conversation history is maintained

🧪 Performance Testing:
- Send multiple messages quickly
- Test with long text inputs
- Verify page remains responsive

🧪 Accessibility Testing:
- Check keyboard navigation
- Verify ARIA labels
- Test screen reader compatibility

SAMPLE PLAYWRIGHT MCP COMMANDS:

1. "Navigate to the Toaster 3000 app and take a screenshot"
2. "Fill the text input with 'Hello Toaster!' and submit the form"
3. "Click on all buttons and verify they work"
4. "Test the dropdown menu functionality"
5. "Scroll through the conversation and verify chat history"

TROUBLESHOOTING:

If tests fail:
1. Check that the app is running on the expected URL
2. Verify environment variables are set correctly
3. Check browser console for JavaScript errors
4. Ensure all required dependencies are installed

Remember: The Toaster 3000 is designed to be enthusiastic about toast,
so expect responses to be very excited about bread and toasting! 🍞
""")
    print("=" * 60)


def show_quick_test_commands():
    """Show quick test commands for immediate use"""
    print("🚀 QUICK TEST COMMANDS FOR PLAYWRIGHT MCP")
    print("=" * 50)
    print("""
Copy and paste these commands into Claude Code to test the Toaster 3000 UI:

1. BASIC PAGE TEST:
"Navigate to http://127.0.0.1:7860 and verify the page loads with the Toaster 3000 title"

2. INTERACTION TEST:
"Type 'What makes perfect toast?' in the text input and click send, then verify the response appears"

3. UI ELEMENTS TEST:
"Check that all main UI components are visible: text input, buttons, dropdowns, and conversation area"

4. MOBILE RESPONSIVE TEST:
"Resize browser to mobile width and verify the layout adapts properly"

5. COMPLETE WORKFLOW TEST:
"Test a full conversation: send a message, verify response, clear chat, and verify reset"
""")
    print("=" * 50)


def main():
    """Main function to run the demo"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--quick":
            show_quick_test_commands()
        elif sys.argv[1] == "--guide":
            show_ui_testing_guide()
        else:
            print("Usage: python test_ui_demo.py [--quick|--guide]")
    else:
        show_ui_testing_guide()
        print("\n" + "🍞" * 20)
        print("Ready to test? Start the Toaster 3000 app and use Playwright MCP!")
        print("🍞" * 20)


if __name__ == "__main__":
    main()