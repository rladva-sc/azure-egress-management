@description('The name of the Azure Egress Management project deployment.')
param projectName string = 'egress-management'

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Deployment environment (dev, test, or prod)')
@allowed([
  'dev'
  'test'
  'prod'
])
param environment string = 'dev'

@description('Storage Account type for metrics data')
@allowed([
  'Standard_LRS'
  'Standard_GRS'
  'Standard_ZRS'
])
param storageAccountType string = 'Standard_LRS'

@description('App Service Plan SKU for dashboard hosting')
@allowed([
  'F1'
  'B1'
  'B2'
  'S1'
  'P1V2'
])
param appServicePlanSku string = 'F1'

@description('Number of days to retain logs in Log Analytics')
@minValue(7)
@maxValue(365)
param logRetentionDays int = 30

@description('Enable the web dashboard')
param enableDashboard bool = true

@description('Enable egress anomaly alerts')
param enableAlerts bool = true

@description('Deploy Python application')
param deployPython bool = true

// Variables
var resourceNamePrefix = '${projectName}-${environment}'
var storageAccountName = replace('${resourceNamePrefix}stg', '-', '')
var appServicePlanName = '${resourceNamePrefix}-plan'
var appServiceName = '${resourceNamePrefix}-app'
var functionAppName = '${resourceNamePrefix}-func'
var appInsightsName = '${resourceNamePrefix}-ai'
var logAnalyticsName = '${resourceNamePrefix}-logs'
var keyVaultName = '${resourceNamePrefix}-kv'
var monitorAlertName = '${resourceNamePrefix}-alert'
var functionWorkerRuntime = 'python'

var containerNames = {
  rawData: 'rawdata'
  processedData: 'processed'
  reports: 'reports'
}

var tags = {
  Project: projectName
  Environment: environment
}

// Storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2021-04-01' = {
  name: toLower(storageAccountName)
  location: location
  tags: tags
  sku: {
    name: storageAccountType
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    encryption: {
      services: {
        file: {
          keyType: 'Account'
          enabled: true
        }
        blob: {
          keyType: 'Account'
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

// Blob Services
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2021-04-01' = {
  name: '${storageAccount.name}/default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    cors: {
      corsRules: []
    }
  }
}

// Container: Raw Data
resource rawDataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-04-01' = {
  name: '${blobService.name}/${containerNames.rawData}'
  properties: {
    publicAccess: 'None'
  }
}

// Container: Processed Data
resource processedDataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-04-01' = {
  name: '${blobService.name}/${containerNames.processedData}'
  properties: {
    publicAccess: 'None'
  }
}

// Container: Reports
resource reportsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-04-01' = {
  name: '${blobService.name}/${containerNames.reports}'
  properties: {
    publicAccess: 'None'
  }
}

// Log Analytics workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: logRetentionDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: 1
    }
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    Flow_Type: 'Redfield'
    Request_Source: 'IbizaAIExtension'
  }
}

// App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2021-02-01' = if (enableDashboard) {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: appServicePlanSku
    tier: appServicePlanSku == 'F1'
      ? 'Free'
      : startsWith(appServicePlanSku, 'B') ? 'Basic' : startsWith(appServicePlanSku, 'S') ? 'Standard' : 'PremiumV2'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// App Service
resource appService 'Microsoft.Web/sites@2021-02-01' = if (enableDashboard && deployPython) {
  name: appServiceName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.10'
      pythonVersion: '3.10'
      alwaysOn: appServicePlanSku != 'F1'
      appSettings: [
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'STORAGE_CONTAINER_RAW'
          value: containerNames.rawData
        }
        {
          name: 'STORAGE_CONTAINER_PROCESSED'
          value: containerNames.processedData
        }
        {
          name: 'STORAGE_CONTAINER_REPORTS'
          value: containerNames.reports
        }
        {
          name: 'ENVIRONMENT'
          value: environment
        }
        {
          name: 'WEBSITE_PYTHONPATH'
          value: '/home/site/wwwroot'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'SCRIPT_STARTUP_COMMAND'
          value: 'gunicorn -b :8000 src.dashboard.app:server'
        }
      ]
    }
  }
}

// Function App
resource functionApp 'Microsoft.Web/sites@2021-02-01' = if (deployPython) {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.10'
      pythonVersion: '3.10'
      alwaysOn: appServicePlanSku != 'F1'
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: functionWorkerRuntime
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'STORAGE_CONTAINER_RAW'
          value: containerNames.rawData
        }
        {
          name: 'STORAGE_CONTAINER_PROCESSED'
          value: containerNames.processedData
        }
        {
          name: 'STORAGE_CONTAINER_REPORTS'
          value: containerNames.reports
        }
        {
          name: 'ENVIRONMENT'
          value: environment
        }
      ]
    }
  }
}

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2021-04-01-preview' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    enabledForDeployment: false
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    tenantId: subscription().tenantId
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: functionApp.identity.principalId
        permissions: {
          keys: [
            'Get'
          ]
          secrets: [
            'Get'
            'List'
          ]
          certificates: [
            'Get'
          ]
        }
      }
    ]
    sku: {
      name: 'standard'
      family: 'A'
    }
  }
}

// Monitor alert
resource monitorAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (enableAlerts) {
  name: monitorAlertName
  location: 'global'
  tags: tags
  properties: {
    description: 'Alert when egress traffic exceeds threshold'
    severity: 2
    enabled: true
    scopes: [
      storageAccount.id
    ]
    evaluationFrequency: 'PT1H'
    windowSize: 'PT1H'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Egress'
          metricName: 'Egress'
          dimensions: []
          operator: 'GreaterThan'
          threshold: 5000000000 // 5GB
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: []
  }
}

// Outputs
output storageAccountName string = storageAccount.name
output appServiceUrl string = enableDashboard ? 'https://${appService.properties.defaultHostName}' : ''
output functionAppUrl string = deployPython ? 'https://${functionApp.properties.defaultHostName}' : ''
output keyVaultName string = keyVault.name
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
