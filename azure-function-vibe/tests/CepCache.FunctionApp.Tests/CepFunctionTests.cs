using System;
using System.Net;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Azure.WebJobs;
using Microsoft.Azure.WebJobs.Extensions.Http;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;
using CepCache.FunctionApp.Services;
using CepCache.FunctionApp.Models;

namespace CepCache.FunctionApp.Tests
{
    public class CepFunctionTests
    {
        private readonly Mock<ICepService> _cepServiceMock;
        private readonly ILogger<GetCepFunction> _logger;

        public CepFunctionTests()
        {
            _cepServiceMock = new Mock<ICepService>();
            _logger = new Mock<ILogger<GetCepFunction>>().Object;
        }

        [Fact]
        public async Task GetCep_ReturnsCachedCep_WhenExistsInCosmosDB()
        {
            // Arrange
            var cep = "01001-000";
            var expectedResult = new CepResult { Cep = cep, Logradouro = "Praça da Sé", Bairro = "Sé", Localidade = "São Paulo", Uf = "SP" };
            _cepServiceMock.Setup(service => service.GetCepAsync(cep)).ReturnsAsync(expectedResult);

            var function = new GetCepFunction(_cepServiceMock.Object);

            var request = new DefaultHttpContext().Request;
            request.QueryString = new QueryString($"?cep={cep}");

            // Act
            var result = await function.Run(request, _logger);

            // Assert
            var okResult = Assert.IsType<OkObjectResult>(result);
            var actualResult = Assert.IsType<CepResult>(okResult.Value);
            Assert.Equal(expectedResult.Cep, actualResult.Cep);
        }

        [Fact]
        public async Task GetCep_ReturnsNotFound_WhenCepDoesNotExist()
        {
            // Arrange
            var cep = "99999-999";
            _cepServiceMock.Setup(service => service.GetCepAsync(cep)).ReturnsAsync((CepResult)null);

            var function = new GetCepFunction(_cepServiceMock.Object);

            var request = new DefaultHttpContext().Request;
            request.QueryString = new QueryString($"?cep={cep}");

            // Act
            var result = await function.Run(request, _logger);

            // Assert
            Assert.IsType<NotFoundResult>(result);
        }

        [Fact]
        public async Task GetCep_ReturnsCepFromApi_WhenNotInCosmosDB()
        {
            // Arrange
            var cep = "01001-000";
            var expectedResult = new CepResult { Cep = cep, Logradouro = "Praça da Sé", Bairro = "Sé", Localidade = "São Paulo", Uf = "SP" };
            _cepServiceMock.Setup(service => service.GetCepAsync(cep)).ReturnsAsync((CepResult)null);
            _cepServiceMock.Setup(service => service.FetchCepFromApiAsync(cep)).ReturnsAsync(expectedResult);

            var function = new GetCepFunction(_cepServiceMock.Object);

            var request = new DefaultHttpContext().Request;
            request.QueryString = new QueryString($"?cep={cep}");

            // Act
            var result = await function.Run(request, _logger);

            // Assert
            var okResult = Assert.IsType<OkObjectResult>(result);
            var actualResult = Assert.IsType<CepResult>(okResult.Value);
            Assert.Equal(expectedResult.Cep, actualResult.Cep);
        }
    }
}