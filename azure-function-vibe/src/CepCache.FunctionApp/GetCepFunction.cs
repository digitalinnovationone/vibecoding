using System.IO;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Azure.WebJobs;
using Microsoft.Azure.WebJobs.Extensions.Http;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;
using CepCache.FunctionApp.Models;
using CepCache.FunctionApp.Services;

namespace CepCache.FunctionApp
{
    public class GetCepFunction
    {
        private readonly ICepService _cepService;

        public GetCepFunction(ICepService cepService)
        {
            _cepService = cepService;
        }

        [FunctionName("GetCep")]
        public async Task<IActionResult> Run(
            [HttpTrigger(AuthorizationLevel.Function, "get", "post", Route = "cep/{cep}")] HttpRequest req,
            string cep,
            ILogger log)
        {
            log.LogInformation($"C# HTTP trigger function processed a request for CEP: {cep}");

            if (string.IsNullOrWhiteSpace(cep))
            {
                return new BadRequestObjectResult("CEP is required.");
            }

            CepResult cepResult = await _cepService.GetCepAsync(cep);

            if (cepResult == null)
            {
                return new NotFoundObjectResult($"CEP {cep} not found.");
            }

            return new OkObjectResult(cepResult);
        }
    }
}