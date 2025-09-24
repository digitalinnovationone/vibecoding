using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Azure.Cosmos;
using Newtonsoft.Json;

namespace CepCache.FunctionApp.Services
{
    public class CosmosRepository
    {
        private readonly CosmosClient _cosmosClient;
        private readonly Container _container;

        public CosmosRepository(string connectionString, string databaseName, string containerName)
        {
            _cosmosClient = new CosmosClient(connectionString);
            _container = _cosmosClient.GetContainer(databaseName, containerName);
        }

        public async Task<CepResult> GetCepAsync(string cep)
        {
            try
            {
                ItemResponse<CepResult> response = await _container.ReadItemAsync<CepResult>(cep, new PartitionKey(cep));
                return response.Resource;
            }
            catch (CosmosException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                return null; // Item not found
            }
        }

        public async Task SaveCepAsync(CepResult cepResult)
        {
            await _container.UpsertItemAsync(cepResult, new PartitionKey(cepResult.Cep));
        }
    }
}