import chainlit as cl

# Sample troubleshooting database
TROUBLESHOOTING_GUIDE = {
    "cnc rough cuts": "Check the tool sharpness and ensure proper feed rate. Adjust spindle speed accordingly.",
    "cnc inaccurate holes": "Calibrate the machine properly. Check tool offsets and alignment.",
    "cnc vibration": "Tighten workpiece holding and ensure the machine is on a stable surface."
}

@cl.on_message
async def on_message(message: cl.Message):
    user_input = message.content.lower()  # Convert input to lowercase for matching
    response = "I'm not sure. Please check the machine settings and try again."

    # Check if any keyword from TROUBLESHOOTING_GUIDE matches user input
    for issue, solution in TROUBLESHOOTING_GUIDE.items():
        if any(word in user_input for word in issue.split()):
            response = solution
            break

    await cl.Message(content=response).send()
