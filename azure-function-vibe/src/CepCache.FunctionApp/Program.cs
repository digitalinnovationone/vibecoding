using Microsoft.Azure.Functions.Extensions.DependencyInjection;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

[assembly: FunctionsStartup(typeof(CepCache.FunctionApp.Startup))]

namespace CepCache.FunctionApp
{
    public class Startup : FunctionsStartup
    {
        public override void Configure(IFunctionsHostBuilder builder)
        {
            // Obtem o contexto (contains IConfiguration)
            var config = builder.GetContext().Configuration;

            // Registra seções fortemente tipadas
            builder.Services.Configure<ViaCepSettings>(config.GetSection("ViaCep"));
            builder.Services.Configure<CosmosSettings>(config.GetSection("Cosmos"));
            builder.Services.Configure<CacheSettings>(config.GetSection("Cache"));

            // Registra serviços - use IHttpClientFactory para o client HTTP
            builder.Services.AddHttpClient<IViaCepClient, ViaCepClient>((sp, client) =>
            {
                var viaCepSettings = sp.GetRequiredService<IOptions<ViaCepSettings>>().Value;
                client.BaseAddress = new Uri(viaCepSettings.BaseUrl);
                // configure timeout, headers etc.
            });

            builder.Services.AddSingleton<ICepService, ViaCepClient>();
            builder.Services.AddSingleton<CosmosRepository>();
        }
    }

    // Classes de configuração (exemplos)
    public class ViaCepSettings { public string BaseUrl { get; set; } = "https://viacep.com.br/ws"; }
    public class CosmosSettings { public string ConnectionString { get; set; } = ""; public string DatabaseId { get; set; } = ""; public string ContainerId { get; set; } = ""; }
    public class CacheSettings { public int TtlMinutes { get; set; } = 1440; }
}