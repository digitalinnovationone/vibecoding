# viacep-cache-func

## Overview
The `viacep-cache-func` project is an Azure Function application designed to cache and retrieve postal code (CEP) information using the ViaCEP API and Azure CosmosDB. The application aims to reduce the number of API calls to ViaCEP by storing previously retrieved CEP data in CosmosDB.

## Project Structure
The project is organized into the following main directories:

- **src**: Contains the source code for the Azure Function application.
  - **CepCache.FunctionApp**: The main function app project.
    - `CepCache.FunctionApp.csproj`: Project file defining dependencies and configurations.
    - `Program.cs`: Entry point for the Azure Function application.
    - `GetCepFunction.cs`: Defines the Azure Function for handling CEP requests.
    - `host.json`: Global configuration options for the Azure Functions host.
    - `local.settings.json`: Local development settings (not included in source control).
    - **Services**: Contains service classes for handling CEP data.
      - `ICepService.cs`: Interface for the CEP service.
      - `ViaCepClient.cs`: Implements the ICepService interface to interact with the ViaCEP API.
      - `CosmosRepository.cs`: Provides methods for interacting with CosmosDB.
    - **Models**: Contains data model classes.
      - `CepResult.cs`: Represents the structure of CEP data.

- **tests**: Contains unit tests for the function app.
  - **CepCache.FunctionApp.Tests**: Project for testing the function app.
    - `CepFunctionTests.cs`: Unit tests for the GetCepFunction.

- **.vscode**: Contains configuration files for the development environment.
  - `launch.json`: Debugging configuration.
  - `tasks.json`: Task definitions for building and running the project.

- **.gitignore**: Specifies files and directories to be ignored by Git.

## Setup Instructions
1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd viacep-cache-func
   ```

2. **Install Dependencies**
   Ensure you have the .NET 9 SDK installed. Run the following command to restore the project dependencies:
   ```bash
   dotnet restore src/CepCache.FunctionApp/CepCache.FunctionApp.csproj
   ```

3. **Configure Local Settings**
   Update the `local.settings.json` file with your CosmosDB connection string and any necessary API keys.

4. **Run the Application**
   You can run the Azure Function locally using the following command:
   ```bash
   func start --project src/CepCache.FunctionApp
   ```

## Usage
To retrieve CEP information, send a request to the Azure Function endpoint. The function will first check CosmosDB for the requested CEP. If the CEP is not found, it will call the ViaCEP API and store the result in CosmosDB for future requests.

## Testing
Unit tests are provided in the `tests/CepCache.FunctionApp.Tests` directory. You can run the tests using the following command:
```bash
dotnet test tests/CepCache.FunctionApp.Tests/CepCache.FunctionApp.Tests.csproj
```

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.