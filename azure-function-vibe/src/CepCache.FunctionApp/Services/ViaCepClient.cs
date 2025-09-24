using System.Net.Http;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Microsoft.Extensions.Logging;

namespace CepCache.FunctionApp.Services
{
    public class ViaCepClient : ICepService
    {
        private readonly HttpClient _httpClient;
        private readonly CosmosRepository _cosmosRepository;
        private readonly ILogger<ViaCepClient> _logger;

        public ViaCepClient(HttpClient httpClient, CosmosRepository cosmosRepository, ILogger<ViaCepClient> logger)
        {
            _httpClient = httpClient;
            _cosmosRepository = cosmosRepository;
            _logger = logger;
        }

        public async Task<CepResult> GetCepAsync(string cep)
        {
            // Check if the CEP exists in CosmosDB
            var cachedResult = await _cosmosRepository.GetCepAsync(cep);
            if (cachedResult != null)
            {
                _logger.LogInformation($"CEP {cep} retrieved from CosmosDB.");
                return cachedResult;
            }

            // If not found in CosmosDB, call the ViaCEP API
            var response = await _httpClient.GetAsync($"https://viacep.com.br/ws/{cep}/json/");
            if (response.IsSuccessStatusCode)
            {
                var jsonResponse = await response.Content.ReadAsStringAsync();
                var cepResult = JsonConvert.DeserializeObject<CepResult>(jsonResponse);

                // Save the result to CosmosDB for future requests
                await _cosmosRepository.SaveCepAsync(cepResult);
                _logger.LogInformation($"CEP {cep} retrieved from ViaCEP API and saved to CosmosDB.");
                return cepResult;
            }

            _logger.LogWarning($"Failed to retrieve CEP {cep} from ViaCEP API.");
            return null;
        }
    }
}