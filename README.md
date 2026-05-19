# StegoVault

A highly secure, premium, and visually striking "Matrix" styled steganography tool.

StegoVault functions as an invisible digital enclave. By dropping your raw files and secret messages into StegoVault, they are cryptographically sealed and injected into the pixels of a standard carrier image (PNG/BMP). The output image looks entirely normal, but contains an AES-256-GCM encrypted payload. Only the possessor of the correct Passphrase can decrypt and extract the files back into the StegoVault workspace.

## Features
- **True Encryption**: Utilizes heavy-duty cryptography (PBKDF2 & AES-256-GCM) to securely encrypt and salt your file data upon injection.
- **LSB Steganography**: Natively hides the encrypted payload inside the Least Significant Bits of an image, making it completely invisible to the naked eye.
- **Cyber-Aesthetic**: Built with a stunning `QSS` terminal stylesheet for a clean, focus-driven user experience.
- **Portable Unified Payload**: Your secret messages and multiple files are automatically bundled into a single compressed stream inside the image. You can safely send this image over the internet or store it on a USB drive without raising suspicion.

## Usage
1. Open the application in **[ ENCODE_MODE ]**.
2. Drag and drop a Carrier Image (PNG/BMP) into the workspace.
3. Type a secret message and/or drag files into the File Workspace to add them to the payload.
4. Set an Encryption Passphrase and click `[ EXECUTE_INJECTION_PROTOCOL ]` to generate the new image.
5. To extract, switch to **[ DECODE_MODE ]**, drop the encoded image, enter the Passphrase, and hit `[ INITIALIZE_DECRYPT ]`.

## Developer Installation
Ensure you have Python 3 installed. Then, use pip to install the required libraries:
```bash
pip install -r requirements.txt
python app_matrix.py
```

## Building the Executable
Because the compiled standalone application size exceeds standard repository file limits, no pre-built `.exe` is provided. However, you can easily compile your own `.exe` from the source code using PyInstaller:

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed --name StegoVault app_matrix.py
```

This will generate a `StegoVault.exe` file inside the `dist` folder. You can then copy it to your Desktop or a USB drive and use StegoVault anywhere!

## License
This project is licensed under the [MIT License](LICENSE). You are free to use, modify, and distribute this software.
