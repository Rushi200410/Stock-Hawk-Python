import mock_generator

if __name__ == "__main__":
    # In production, this would start the live Kite connection.
    # For now, it starts our simulation.
    mock_generator.start_simulation()