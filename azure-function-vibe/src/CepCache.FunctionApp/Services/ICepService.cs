namespace CepCache.FunctionApp.Services
{
    public interface ICepService
    {
        Task<CepResult> GetCepAsync(string cep);
    }
}