# n8n built-in nodes (reference)

Generated inventory of workflow node implementations checked out from the n8n monorepo. Paths are relative to the **n8n repository root** (sibling clone: `../n8n` next to DocRouter unless you relocated it).

## Versions (at generation time)

- Monorepo / `n8n-nodes-base`: **1.72.0** (`../n8n/package.json`).
- Package `@n8n/nodes-langchain` (bundled AI/LangChain nodes): **1.72.0**.

## Where nodes ship from

| Package | Purpose | Source root (`../n8n/...`) |
|--------|---------|------------------------------|
| **`n8n-nodes-base`** | Core/community integrations (HTTP, SaaS connectors, helpers, transforms) | [`packages/nodes-base/nodes/`](../../n8n/packages/nodes-base/nodes/) |
| **`@n8n/nodes-langchain`** | LLM embeddings, chains, agents, vector stores, document loaders | [`packages/@n8n/nodes-langchain/nodes/`](../../n8n/packages/@n8n/nodes-langchain/nodes/) |

Compiled output referenced at runtime lives under each package's **`dist/`** tree; the authoring source is always the **`*.node.ts`** file alongside credentials and descriptors in the same integration folder.

## Coverage summary (`n8n-nodes-base`)

*Total node implementations:* **506** `*.node.ts` files.

| Integration folder (under `packages/nodes-base/nodes/`) | Node `.ts` files |
|--------------------------------------------------------|------------------|
| `ActionNetwork/` | 1 |
| `ActiveCampaign/` | 2 |
| `AcuityScheduling/` | 1 |
| `Adalo/` | 1 |
| `Affinity/` | 2 |
| `AgileCrm/` | 1 |
| `Airtable/` | 4 |
| `AiTransform/` | 1 |
| `Amqp/` | 2 |
| `ApiTemplateIo/` | 1 |
| `Asana/` | 2 |
| `Automizy/` | 1 |
| `Autopilot/` | 2 |
| `Aws/` | 15 |
| `BambooHr/` | 1 |
| `Bannerbear/` | 1 |
| `Baserow/` | 1 |
| `Beeminder/` | 1 |
| `Bitbucket/` | 1 |
| `Bitly/` | 1 |
| `Bitwarden/` | 1 |
| `Box/` | 2 |
| `Brandfetch/` | 1 |
| `Brevo/` | 2 |
| `Bubble/` | 1 |
| `Cal/` | 1 |
| `Calendly/` | 1 |
| `Chargebee/` | 2 |
| `CircleCi/` | 1 |
| `Cisco/` | 2 |
| `Clearbit/` | 1 |
| `ClickUp/` | 2 |
| `Clockify/` | 2 |
| `Cloudflare/` | 1 |
| `Cockpit/` | 1 |
| `Coda/` | 1 |
| `Code/` | 1 |
| `CoinGecko/` | 1 |
| `CompareDatasets/` | 1 |
| `Compression/` | 1 |
| `Contentful/` | 1 |
| `ConvertKit/` | 2 |
| `Copper/` | 2 |
| `Cortex/` | 1 |
| `CrateDb/` | 1 |
| `Cron/` | 1 |
| `CrowdDev/` | 2 |
| `Crypto/` | 1 |
| `CustomerIo/` | 2 |
| `DateTime/` | 3 |
| `DebugHelper/` | 1 |
| `DeepL/` | 1 |
| `Demio/` | 1 |
| `Dhl/` | 1 |
| `Discord/` | 3 |
| `Discourse/` | 1 |
| `Disqus/` | 1 |
| `Drift/` | 1 |
| `Dropbox/` | 1 |
| `Dropcontact/` | 1 |
| `E2eTest/` | 1 |
| `EditImage/` | 1 |
| `Egoi/` | 1 |
| `Elastic/` | 2 |
| `EmailReadImap/` | 3 |
| `EmailSend/` | 3 |
| `Emelia/` | 2 |
| `ERPNext/` | 1 |
| `ErrorTrigger/` | 1 |
| `Eventbrite/` | 1 |
| `ExecuteCommand/` | 1 |
| `ExecuteWorkflow/` | 1 |
| `ExecuteWorkflowTrigger/` | 1 |
| `ExecutionData/` | 1 |
| `Facebook/` | 2 |
| `FacebookLeadAds/` | 1 |
| `Figma/` | 1 |
| `FileMaker/` | 1 |
| `Files/` | 3 |
| `Filter/` | 3 |
| `Flow/` | 2 |
| `Form/` | 4 |
| `FormIo/` | 1 |
| `Formstack/` | 1 |
| `Freshdesk/` | 1 |
| `Freshservice/` | 1 |
| `FreshworksCrm/` | 1 |
| `Ftp/` | 1 |
| `Function/` | 1 |
| `FunctionItem/` | 1 |
| `GetResponse/` | 2 |
| `Ghost/` | 1 |
| `Git/` | 1 |
| `Github/` | 2 |
| `Gitlab/` | 2 |
| `Gong/` | 1 |
| `Google/` | 37 |
| `Gotify/` | 1 |
| `GoToWebinar/` | 1 |
| `Grafana/` | 1 |
| `GraphQL/` | 1 |
| `Grist/` | 1 |
| `Gumroad/` | 1 |
| `HackerNews/` | 1 |
| `HaloPSA/` | 1 |
| `Harvest/` | 1 |
| `HelpScout/` | 2 |
| `HighLevel/` | 3 |
| `HomeAssistant/` | 1 |
| `Html/` | 1 |
| `HtmlExtract/` | 1 |
| `HttpRequest/` | 4 |
| `Hubspot/` | 4 |
| `HumanticAI/` | 1 |
| `Hunter/` | 1 |
| `ICalendar/` | 1 |
| `If/` | 3 |
| `Intercom/` | 1 |
| `Interval/` | 1 |
| `InvoiceNinja/` | 2 |
| `ItemLists/` | 4 |
| `Iterable/` | 1 |
| `Jenkins/` | 1 |
| `Jira/` | 2 |
| `JotForm/` | 1 |
| `Jwt/` | 1 |
| `Kafka/` | 2 |
| `Keap/` | 2 |
| `Kitemaker/` | 1 |
| `KoBoToolbox/` | 2 |
| `Ldap/` | 1 |
| `Lemlist/` | 4 |
| `Line/` | 1 |
| `Linear/` | 2 |
| `LingvaNex/` | 1 |
| `LinkedIn/` | 1 |
| `LocalFileTrigger/` | 1 |
| `LoneScale/` | 2 |
| `Magento/` | 1 |
| `Mailcheck/` | 1 |
| `Mailchimp/` | 2 |
| `MailerLite/` | 2 |
| `Mailgun/` | 1 |
| `Mailjet/` | 2 |
| `Mandrill/` | 1 |
| `ManualTrigger/` | 1 |
| `Markdown/` | 1 |
| `Marketstack/` | 1 |
| `Matrix/` | 1 |
| `Mattermost/` | 2 |
| `Mautic/` | 2 |
| `Medium/` | 1 |
| `Merge/` | 4 |
| `MessageBird/` | 1 |
| `Metabase/` | 1 |
| `Microsoft/` | 16 |
| `Mindee/` | 1 |
| `Misp/` | 1 |
| `Mocean/` | 1 |
| `MondayCom/` | 1 |
| `MongoDb/` | 1 |
| `MonicaCrm/` | 1 |
| `MoveBinaryData/` | 1 |
| `MQTT/` | 2 |
| `Msg91/` | 1 |
| `MySql/` | 3 |
| `N8n/` | 1 |
| `N8nTrainingCustomerDatastore/` | 1 |
| `N8nTrainingCustomerMessenger/` | 1 |
| `N8nTrigger/` | 1 |
| `Nasa/` | 1 |
| `Netlify/` | 2 |
| `Netscaler/` | 1 |
| `NextCloud/` | 1 |
| `NocoDB/` | 1 |
| `NoOp/` | 1 |
| `Notion/` | 4 |
| `Npm/` | 1 |
| `Odoo/` | 1 |
| `Okta/` | 1 |
| `OneSimpleApi/` | 1 |
| `Onfleet/` | 2 |
| `OpenAi/` | 1 |
| `OpenThesaurus/` | 1 |
| `OpenWeatherMap/` | 1 |
| `Orbit/` | 1 |
| `Oura/` | 1 |
| `Paddle/` | 1 |
| `PagerDuty/` | 1 |
| `PayPal/` | 2 |
| `Peekalink/` | 1 |
| `Phantombuster/` | 1 |
| `PhilipsHue/` | 1 |
| `Pipedrive/` | 2 |
| `Plivo/` | 1 |
| `PostBin/` | 1 |
| `Postgres/` | 4 |
| `PostHog/` | 1 |
| `Postmark/` | 1 |
| `ProfitWell/` | 1 |
| `Pushbullet/` | 1 |
| `Pushcut/` | 2 |
| `Pushover/` | 1 |
| `QuestDb/` | 1 |
| `QuickBase/` | 1 |
| `QuickBooks/` | 1 |
| `QuickChart/` | 1 |
| `RabbitMQ/` | 2 |
| `Raindrop/` | 1 |
| `ReadBinaryFile/` | 1 |
| `ReadBinaryFiles/` | 1 |
| `ReadPdf/` | 1 |
| `Reddit/` | 1 |
| `Redis/` | 2 |
| `RenameKeys/` | 1 |
| `RespondToWebhook/` | 1 |
| `Rocketchat/` | 1 |
| `RssFeedRead/` | 2 |
| `Rundeck/` | 1 |
| `S3/` | 1 |
| `Salesforce/` | 2 |
| `Salesmate/` | 1 |
| `Schedule/` | 1 |
| `SeaTable/` | 2 |
| `SecurityScorecard/` | 1 |
| `Segment/` | 1 |
| `SendGrid/` | 1 |
| `Sendy/` | 1 |
| `SentryIo/` | 1 |
| `ServiceNow/` | 1 |
| `Set/` | 3 |
| `Shopify/` | 2 |
| `Signl4/` | 1 |
| `Simulate/` | 2 |
| `Slack/` | 4 |
| `Sms77/` | 1 |
| `Snowflake/` | 1 |
| `SplitInBatches/` | 4 |
| `Splunk/` | 3 |
| `Spontit/` | 1 |
| `Spotify/` | 1 |
| `SpreadsheetFile/` | 3 |
| `SseTrigger/` | 1 |
| `Ssh/` | 1 |
| `Stackby/` | 1 |
| `Start/` | 1 |
| `StickyNote/` | 1 |
| `StopAndError/` | 1 |
| `Storyblok/` | 1 |
| `Strapi/` | 1 |
| `Strava/` | 2 |
| `Stripe/` | 2 |
| `Supabase/` | 1 |
| `SurveyMonkey/` | 1 |
| `Switch/` | 4 |
| `SyncroMSP/` | 2 |
| `Taiga/` | 2 |
| `Tapfiliate/` | 1 |
| `Telegram/` | 2 |
| `TheHive/` | 2 |
| `TheHiveProject/` | 2 |
| `TimescaleDb/` | 1 |
| `Todoist/` | 3 |
| `Toggl/` | 1 |
| `Totp/` | 1 |
| `Transform/` | 8 |
| `TravisCi/` | 1 |
| `Trello/` | 2 |
| `Twake/` | 1 |
| `Twilio/` | 2 |
| `Twist/` | 1 |
| `Twitter/` | 3 |
| `Typeform/` | 1 |
| `UnleashedSoftware/` | 1 |
| `Uplead/` | 1 |
| `UProc/` | 1 |
| `UptimeRobot/` | 1 |
| `UrlScanIo/` | 1 |
| `Venafi/` | 4 |
| `Vero/` | 1 |
| `Vonage/` | 1 |
| `Wait/` | 1 |
| `Webflow/` | 6 |
| `Webhook/` | 1 |
| `Wekan/` | 1 |
| `WhatsApp/` | 2 |
| `Wise/` | 2 |
| `WooCommerce/` | 2 |
| `Wordpress/` | 1 |
| `Workable/` | 1 |
| `WorkflowTrigger/` | 1 |
| `WriteBinaryFile/` | 1 |
| `Wufoo/` | 1 |
| `Xero/` | 1 |
| `Xml/` | 1 |
| `Yourls/` | 1 |
| `Zammad/` | 1 |
| `Zendesk/` | 2 |
| `Zoho/` | 1 |
| `Zoom/` | 1 |
| `Zulip/` | 1 |

## Coverage summary (`@n8n/nodes-langchain`)

*Total node implementations:* **79** `*.node.ts` files.

| Category folder (`packages/@n8n/nodes-langchain/nodes/...`) | Node `.ts` files |
|------------------------------------------------------------|------------------|
| `agents/` | 2 |
| `chains/` | 8 |
| `code/` | 1 |
| `document_loaders/` | 4 |
| `embeddings/` | 8 |
| `llms/` | 13 |
| `memory/` | 8 |
| `output_parser/` | 3 |
| `retrievers/` | 4 |
| `text_splitters/` | 3 |
| `tools/` | 8 |
| `trigger/` | 2 |
| `vector_store/` | 14 |
| `vendors/` | 1 |

## Full listing — `n8n-nodes-base` (`*.node.ts`)

Sorted alphabetically by path (506 entries).

- `packages/nodes-base/nodes/ActionNetwork/ActionNetwork.node.ts`
- `packages/nodes-base/nodes/ActiveCampaign/ActiveCampaign.node.ts`
- `packages/nodes-base/nodes/ActiveCampaign/ActiveCampaignTrigger.node.ts`
- `packages/nodes-base/nodes/AcuityScheduling/AcuitySchedulingTrigger.node.ts`
- `packages/nodes-base/nodes/Adalo/Adalo.node.ts`
- `packages/nodes-base/nodes/Affinity/Affinity.node.ts`
- `packages/nodes-base/nodes/Affinity/AffinityTrigger.node.ts`
- `packages/nodes-base/nodes/AgileCrm/AgileCrm.node.ts`
- `packages/nodes-base/nodes/AiTransform/AiTransform.node.ts`
- `packages/nodes-base/nodes/Airtable/Airtable.node.ts`
- `packages/nodes-base/nodes/Airtable/AirtableTrigger.node.ts`
- `packages/nodes-base/nodes/Airtable/v1/AirtableV1.node.ts`
- `packages/nodes-base/nodes/Airtable/v2/AirtableV2.node.ts`
- `packages/nodes-base/nodes/Amqp/Amqp.node.ts`
- `packages/nodes-base/nodes/Amqp/AmqpTrigger.node.ts`
- `packages/nodes-base/nodes/ApiTemplateIo/ApiTemplateIo.node.ts`
- `packages/nodes-base/nodes/Asana/Asana.node.ts`
- `packages/nodes-base/nodes/Asana/AsanaTrigger.node.ts`
- `packages/nodes-base/nodes/Automizy/Automizy.node.ts`
- `packages/nodes-base/nodes/Autopilot/Autopilot.node.ts`
- `packages/nodes-base/nodes/Autopilot/AutopilotTrigger.node.ts`
- `packages/nodes-base/nodes/Aws/AwsLambda.node.ts`
- `packages/nodes-base/nodes/Aws/AwsSns.node.ts`
- `packages/nodes-base/nodes/Aws/AwsSnsTrigger.node.ts`
- `packages/nodes-base/nodes/Aws/CertificateManager/AwsCertificateManager.node.ts`
- `packages/nodes-base/nodes/Aws/Comprehend/AwsComprehend.node.ts`
- `packages/nodes-base/nodes/Aws/DynamoDB/AwsDynamoDB.node.ts`
- `packages/nodes-base/nodes/Aws/ELB/AwsElb.node.ts`
- `packages/nodes-base/nodes/Aws/Rekognition/AwsRekognition.node.ts`
- `packages/nodes-base/nodes/Aws/S3/AwsS3.node.ts`
- `packages/nodes-base/nodes/Aws/S3/V1/AwsS3V1.node.ts`
- `packages/nodes-base/nodes/Aws/S3/V2/AwsS3V2.node.ts`
- `packages/nodes-base/nodes/Aws/SES/AwsSes.node.ts`
- `packages/nodes-base/nodes/Aws/SQS/AwsSqs.node.ts`
- `packages/nodes-base/nodes/Aws/Textract/AwsTextract.node.ts`
- `packages/nodes-base/nodes/Aws/Transcribe/AwsTranscribe.node.ts`
- `packages/nodes-base/nodes/BambooHr/BambooHr.node.ts`
- `packages/nodes-base/nodes/Bannerbear/Bannerbear.node.ts`
- `packages/nodes-base/nodes/Baserow/Baserow.node.ts`
- `packages/nodes-base/nodes/Beeminder/Beeminder.node.ts`
- `packages/nodes-base/nodes/Bitbucket/BitbucketTrigger.node.ts`
- `packages/nodes-base/nodes/Bitly/Bitly.node.ts`
- `packages/nodes-base/nodes/Bitwarden/Bitwarden.node.ts`
- `packages/nodes-base/nodes/Box/Box.node.ts`
- `packages/nodes-base/nodes/Box/BoxTrigger.node.ts`
- `packages/nodes-base/nodes/Brandfetch/Brandfetch.node.ts`
- `packages/nodes-base/nodes/Brevo/Brevo.node.ts`
- `packages/nodes-base/nodes/Brevo/BrevoTrigger.node.ts`
- `packages/nodes-base/nodes/Bubble/Bubble.node.ts`
- `packages/nodes-base/nodes/Cal/CalTrigger.node.ts`
- `packages/nodes-base/nodes/Calendly/CalendlyTrigger.node.ts`
- `packages/nodes-base/nodes/Chargebee/Chargebee.node.ts`
- `packages/nodes-base/nodes/Chargebee/ChargebeeTrigger.node.ts`
- `packages/nodes-base/nodes/CircleCi/CircleCi.node.ts`
- `packages/nodes-base/nodes/Cisco/Webex/CiscoWebex.node.ts`
- `packages/nodes-base/nodes/Cisco/Webex/CiscoWebexTrigger.node.ts`
- `packages/nodes-base/nodes/Clearbit/Clearbit.node.ts`
- `packages/nodes-base/nodes/ClickUp/ClickUp.node.ts`
- `packages/nodes-base/nodes/ClickUp/ClickUpTrigger.node.ts`
- `packages/nodes-base/nodes/Clockify/Clockify.node.ts`
- `packages/nodes-base/nodes/Clockify/ClockifyTrigger.node.ts`
- `packages/nodes-base/nodes/Cloudflare/Cloudflare.node.ts`
- `packages/nodes-base/nodes/Cockpit/Cockpit.node.ts`
- `packages/nodes-base/nodes/Coda/Coda.node.ts`
- `packages/nodes-base/nodes/Code/Code.node.ts`
- `packages/nodes-base/nodes/CoinGecko/CoinGecko.node.ts`
- `packages/nodes-base/nodes/CompareDatasets/CompareDatasets.node.ts`
- `packages/nodes-base/nodes/Compression/Compression.node.ts`
- `packages/nodes-base/nodes/Contentful/Contentful.node.ts`
- `packages/nodes-base/nodes/ConvertKit/ConvertKit.node.ts`
- `packages/nodes-base/nodes/ConvertKit/ConvertKitTrigger.node.ts`
- `packages/nodes-base/nodes/Copper/Copper.node.ts`
- `packages/nodes-base/nodes/Copper/CopperTrigger.node.ts`
- `packages/nodes-base/nodes/Cortex/Cortex.node.ts`
- `packages/nodes-base/nodes/CrateDb/CrateDb.node.ts`
- `packages/nodes-base/nodes/Cron/Cron.node.ts`
- `packages/nodes-base/nodes/CrowdDev/CrowdDev.node.ts`
- `packages/nodes-base/nodes/CrowdDev/CrowdDevTrigger.node.ts`
- `packages/nodes-base/nodes/Crypto/Crypto.node.ts`
- `packages/nodes-base/nodes/CustomerIo/CustomerIo.node.ts`
- `packages/nodes-base/nodes/CustomerIo/CustomerIoTrigger.node.ts`
- `packages/nodes-base/nodes/DateTime/DateTime.node.ts`
- `packages/nodes-base/nodes/DateTime/V1/DateTimeV1.node.ts`
- `packages/nodes-base/nodes/DateTime/V2/DateTimeV2.node.ts`
- `packages/nodes-base/nodes/DebugHelper/DebugHelper.node.ts`
- `packages/nodes-base/nodes/DeepL/DeepL.node.ts`
- `packages/nodes-base/nodes/Demio/Demio.node.ts`
- `packages/nodes-base/nodes/Dhl/Dhl.node.ts`
- `packages/nodes-base/nodes/Discord/Discord.node.ts`
- `packages/nodes-base/nodes/Discord/v1/DiscordV1.node.ts`
- `packages/nodes-base/nodes/Discord/v2/DiscordV2.node.ts`
- `packages/nodes-base/nodes/Discourse/Discourse.node.ts`
- `packages/nodes-base/nodes/Disqus/Disqus.node.ts`
- `packages/nodes-base/nodes/Drift/Drift.node.ts`
- `packages/nodes-base/nodes/Dropbox/Dropbox.node.ts`
- `packages/nodes-base/nodes/Dropcontact/Dropcontact.node.ts`
- `packages/nodes-base/nodes/E2eTest/E2eTest.node.ts`
- `packages/nodes-base/nodes/ERPNext/ERPNext.node.ts`
- `packages/nodes-base/nodes/EditImage/EditImage.node.ts`
- `packages/nodes-base/nodes/Egoi/Egoi.node.ts`
- `packages/nodes-base/nodes/Elastic/ElasticSecurity/ElasticSecurity.node.ts`
- `packages/nodes-base/nodes/Elastic/Elasticsearch/Elasticsearch.node.ts`
- `packages/nodes-base/nodes/EmailReadImap/EmailReadImap.node.ts`
- `packages/nodes-base/nodes/EmailReadImap/v1/EmailReadImapV1.node.ts`
- `packages/nodes-base/nodes/EmailReadImap/v2/EmailReadImapV2.node.ts`
- `packages/nodes-base/nodes/EmailSend/EmailSend.node.ts`
- `packages/nodes-base/nodes/EmailSend/v1/EmailSendV1.node.ts`
- `packages/nodes-base/nodes/EmailSend/v2/EmailSendV2.node.ts`
- `packages/nodes-base/nodes/Emelia/Emelia.node.ts`
- `packages/nodes-base/nodes/Emelia/EmeliaTrigger.node.ts`
- `packages/nodes-base/nodes/ErrorTrigger/ErrorTrigger.node.ts`
- `packages/nodes-base/nodes/Eventbrite/EventbriteTrigger.node.ts`
- `packages/nodes-base/nodes/ExecuteCommand/ExecuteCommand.node.ts`
- `packages/nodes-base/nodes/ExecuteWorkflow/ExecuteWorkflow.node.ts`
- `packages/nodes-base/nodes/ExecuteWorkflowTrigger/ExecuteWorkflowTrigger.node.ts`
- `packages/nodes-base/nodes/ExecutionData/ExecutionData.node.ts`
- `packages/nodes-base/nodes/Facebook/FacebookGraphApi.node.ts`
- `packages/nodes-base/nodes/Facebook/FacebookTrigger.node.ts`
- `packages/nodes-base/nodes/FacebookLeadAds/FacebookLeadAdsTrigger.node.ts`
- `packages/nodes-base/nodes/Figma/FigmaTrigger.node.ts`
- `packages/nodes-base/nodes/FileMaker/FileMaker.node.ts`
- `packages/nodes-base/nodes/Files/ConvertToFile/ConvertToFile.node.ts`
- `packages/nodes-base/nodes/Files/ExtractFromFile/ExtractFromFile.node.ts`
- `packages/nodes-base/nodes/Files/ReadWriteFile/ReadWriteFile.node.ts`
- `packages/nodes-base/nodes/Filter/Filter.node.ts`
- `packages/nodes-base/nodes/Filter/V1/FilterV1.node.ts`
- `packages/nodes-base/nodes/Filter/V2/FilterV2.node.ts`
- `packages/nodes-base/nodes/Flow/Flow.node.ts`
- `packages/nodes-base/nodes/Flow/FlowTrigger.node.ts`
- `packages/nodes-base/nodes/Form/Form.node.ts`
- `packages/nodes-base/nodes/Form/FormTrigger.node.ts`
- `packages/nodes-base/nodes/Form/v1/FormTriggerV1.node.ts`
- `packages/nodes-base/nodes/Form/v2/FormTriggerV2.node.ts`
- `packages/nodes-base/nodes/FormIo/FormIoTrigger.node.ts`
- `packages/nodes-base/nodes/Formstack/FormstackTrigger.node.ts`
- `packages/nodes-base/nodes/Freshdesk/Freshdesk.node.ts`
- `packages/nodes-base/nodes/Freshservice/Freshservice.node.ts`
- `packages/nodes-base/nodes/FreshworksCrm/FreshworksCrm.node.ts`
- `packages/nodes-base/nodes/Ftp/Ftp.node.ts`
- `packages/nodes-base/nodes/Function/Function.node.ts`
- `packages/nodes-base/nodes/FunctionItem/FunctionItem.node.ts`
- `packages/nodes-base/nodes/GetResponse/GetResponse.node.ts`
- `packages/nodes-base/nodes/GetResponse/GetResponseTrigger.node.ts`
- `packages/nodes-base/nodes/Ghost/Ghost.node.ts`
- `packages/nodes-base/nodes/Git/Git.node.ts`
- `packages/nodes-base/nodes/Github/Github.node.ts`
- `packages/nodes-base/nodes/Github/GithubTrigger.node.ts`
- `packages/nodes-base/nodes/Gitlab/Gitlab.node.ts`
- `packages/nodes-base/nodes/Gitlab/GitlabTrigger.node.ts`
- `packages/nodes-base/nodes/GoToWebinar/GoToWebinar.node.ts`
- `packages/nodes-base/nodes/Gong/Gong.node.ts`
- `packages/nodes-base/nodes/Google/Ads/GoogleAds.node.ts`
- `packages/nodes-base/nodes/Google/Analytics/GoogleAnalytics.node.ts`
- `packages/nodes-base/nodes/Google/Analytics/v1/GoogleAnalyticsV1.node.ts`
- `packages/nodes-base/nodes/Google/Analytics/v2/GoogleAnalyticsV2.node.ts`
- `packages/nodes-base/nodes/Google/BigQuery/GoogleBigQuery.node.ts`
- `packages/nodes-base/nodes/Google/BigQuery/v1/GoogleBigQueryV1.node.ts`
- `packages/nodes-base/nodes/Google/BigQuery/v2/GoogleBigQueryV2.node.ts`
- `packages/nodes-base/nodes/Google/Books/GoogleBooks.node.ts`
- `packages/nodes-base/nodes/Google/BusinessProfile/GoogleBusinessProfile.node.ts`
- `packages/nodes-base/nodes/Google/BusinessProfile/GoogleBusinessProfileTrigger.node.ts`
- `packages/nodes-base/nodes/Google/Calendar/GoogleCalendar.node.ts`
- `packages/nodes-base/nodes/Google/Calendar/GoogleCalendarTrigger.node.ts`
- `packages/nodes-base/nodes/Google/Chat/GoogleChat.node.ts`
- `packages/nodes-base/nodes/Google/CloudNaturalLanguage/GoogleCloudNaturalLanguage.node.ts`
- `packages/nodes-base/nodes/Google/CloudStorage/GoogleCloudStorage.node.ts`
- `packages/nodes-base/nodes/Google/Contacts/GoogleContacts.node.ts`
- `packages/nodes-base/nodes/Google/Docs/GoogleDocs.node.ts`
- `packages/nodes-base/nodes/Google/Drive/GoogleDrive.node.ts`
- `packages/nodes-base/nodes/Google/Drive/GoogleDriveTrigger.node.ts`
- `packages/nodes-base/nodes/Google/Drive/v1/GoogleDriveV1.node.ts`
- `packages/nodes-base/nodes/Google/Drive/v2/GoogleDriveV2.node.ts`
- `packages/nodes-base/nodes/Google/Firebase/CloudFirestore/GoogleFirebaseCloudFirestore.node.ts`
- `packages/nodes-base/nodes/Google/Firebase/RealtimeDatabase/GoogleFirebaseRealtimeDatabase.node.ts`
- `packages/nodes-base/nodes/Google/GSuiteAdmin/GSuiteAdmin.node.ts`
- `packages/nodes-base/nodes/Google/Gmail/Gmail.node.ts`
- `packages/nodes-base/nodes/Google/Gmail/GmailTrigger.node.ts`
- `packages/nodes-base/nodes/Google/Gmail/v1/GmailV1.node.ts`
- `packages/nodes-base/nodes/Google/Gmail/v2/GmailV2.node.ts`
- `packages/nodes-base/nodes/Google/Perspective/GooglePerspective.node.ts`
- `packages/nodes-base/nodes/Google/Sheet/GoogleSheets.node.ts`
- `packages/nodes-base/nodes/Google/Sheet/GoogleSheetsTrigger.node.ts`
- `packages/nodes-base/nodes/Google/Sheet/v1/GoogleSheetsV1.node.ts`
- `packages/nodes-base/nodes/Google/Sheet/v2/GoogleSheetsV2.node.ts`
- `packages/nodes-base/nodes/Google/Slides/GoogleSlides.node.ts`
- `packages/nodes-base/nodes/Google/Task/GoogleTasks.node.ts`
- `packages/nodes-base/nodes/Google/Translate/GoogleTranslate.node.ts`
- `packages/nodes-base/nodes/Google/YouTube/YouTube.node.ts`
- `packages/nodes-base/nodes/Gotify/Gotify.node.ts`
- `packages/nodes-base/nodes/Grafana/Grafana.node.ts`
- `packages/nodes-base/nodes/GraphQL/GraphQL.node.ts`
- `packages/nodes-base/nodes/Grist/Grist.node.ts`
- `packages/nodes-base/nodes/Gumroad/GumroadTrigger.node.ts`
- `packages/nodes-base/nodes/HackerNews/HackerNews.node.ts`
- `packages/nodes-base/nodes/HaloPSA/HaloPSA.node.ts`
- `packages/nodes-base/nodes/Harvest/Harvest.node.ts`
- `packages/nodes-base/nodes/HelpScout/HelpScout.node.ts`
- `packages/nodes-base/nodes/HelpScout/HelpScoutTrigger.node.ts`
- `packages/nodes-base/nodes/HighLevel/HighLevel.node.ts`
- `packages/nodes-base/nodes/HighLevel/v1/HighLevelV1.node.ts`
- `packages/nodes-base/nodes/HighLevel/v2/HighLevelV2.node.ts`
- `packages/nodes-base/nodes/HomeAssistant/HomeAssistant.node.ts`
- `packages/nodes-base/nodes/Html/Html.node.ts`
- `packages/nodes-base/nodes/HtmlExtract/HtmlExtract.node.ts`
- `packages/nodes-base/nodes/HttpRequest/HttpRequest.node.ts`
- `packages/nodes-base/nodes/HttpRequest/V1/HttpRequestV1.node.ts`
- `packages/nodes-base/nodes/HttpRequest/V2/HttpRequestV2.node.ts`
- `packages/nodes-base/nodes/HttpRequest/V3/HttpRequestV3.node.ts`
- `packages/nodes-base/nodes/Hubspot/Hubspot.node.ts`
- `packages/nodes-base/nodes/Hubspot/HubspotTrigger.node.ts`
- `packages/nodes-base/nodes/Hubspot/V1/HubspotV1.node.ts`
- `packages/nodes-base/nodes/Hubspot/V2/HubspotV2.node.ts`
- `packages/nodes-base/nodes/HumanticAI/HumanticAi.node.ts`
- `packages/nodes-base/nodes/Hunter/Hunter.node.ts`
- `packages/nodes-base/nodes/ICalendar/ICalendar.node.ts`
- `packages/nodes-base/nodes/If/If.node.ts`
- `packages/nodes-base/nodes/If/V1/IfV1.node.ts`
- `packages/nodes-base/nodes/If/V2/IfV2.node.ts`
- `packages/nodes-base/nodes/Intercom/Intercom.node.ts`
- `packages/nodes-base/nodes/Interval/Interval.node.ts`
- `packages/nodes-base/nodes/InvoiceNinja/InvoiceNinja.node.ts`
- `packages/nodes-base/nodes/InvoiceNinja/InvoiceNinjaTrigger.node.ts`
- `packages/nodes-base/nodes/ItemLists/ItemLists.node.ts`
- `packages/nodes-base/nodes/ItemLists/V1/ItemListsV1.node.ts`
- `packages/nodes-base/nodes/ItemLists/V2/ItemListsV2.node.ts`
- `packages/nodes-base/nodes/ItemLists/V3/ItemListsV3.node.ts`
- `packages/nodes-base/nodes/Iterable/Iterable.node.ts`
- `packages/nodes-base/nodes/Jenkins/Jenkins.node.ts`
- `packages/nodes-base/nodes/Jira/Jira.node.ts`
- `packages/nodes-base/nodes/Jira/JiraTrigger.node.ts`
- `packages/nodes-base/nodes/JotForm/JotFormTrigger.node.ts`
- `packages/nodes-base/nodes/Jwt/Jwt.node.ts`
- `packages/nodes-base/nodes/Kafka/Kafka.node.ts`
- `packages/nodes-base/nodes/Kafka/KafkaTrigger.node.ts`
- `packages/nodes-base/nodes/Keap/Keap.node.ts`
- `packages/nodes-base/nodes/Keap/KeapTrigger.node.ts`
- `packages/nodes-base/nodes/Kitemaker/Kitemaker.node.ts`
- `packages/nodes-base/nodes/KoBoToolbox/KoBoToolbox.node.ts`
- `packages/nodes-base/nodes/KoBoToolbox/KoBoToolboxTrigger.node.ts`
- `packages/nodes-base/nodes/Ldap/Ldap.node.ts`
- `packages/nodes-base/nodes/Lemlist/Lemlist.node.ts`
- `packages/nodes-base/nodes/Lemlist/LemlistTrigger.node.ts`
- `packages/nodes-base/nodes/Lemlist/v1/LemlistV1.node.ts`
- `packages/nodes-base/nodes/Lemlist/v2/LemlistV2.node.ts`
- `packages/nodes-base/nodes/Line/Line.node.ts`
- `packages/nodes-base/nodes/Linear/Linear.node.ts`
- `packages/nodes-base/nodes/Linear/LinearTrigger.node.ts`
- `packages/nodes-base/nodes/LingvaNex/LingvaNex.node.ts`
- `packages/nodes-base/nodes/LinkedIn/LinkedIn.node.ts`
- `packages/nodes-base/nodes/LocalFileTrigger/LocalFileTrigger.node.ts`
- `packages/nodes-base/nodes/LoneScale/LoneScale.node.ts`
- `packages/nodes-base/nodes/LoneScale/LoneScaleTrigger.node.ts`
- `packages/nodes-base/nodes/MQTT/Mqtt.node.ts`
- `packages/nodes-base/nodes/MQTT/MqttTrigger.node.ts`
- `packages/nodes-base/nodes/Magento/Magento2.node.ts`
- `packages/nodes-base/nodes/Mailcheck/Mailcheck.node.ts`
- `packages/nodes-base/nodes/Mailchimp/Mailchimp.node.ts`
- `packages/nodes-base/nodes/Mailchimp/MailchimpTrigger.node.ts`
- `packages/nodes-base/nodes/MailerLite/MailerLite.node.ts`
- `packages/nodes-base/nodes/MailerLite/MailerLiteTrigger.node.ts`
- `packages/nodes-base/nodes/Mailgun/Mailgun.node.ts`
- `packages/nodes-base/nodes/Mailjet/Mailjet.node.ts`
- `packages/nodes-base/nodes/Mailjet/MailjetTrigger.node.ts`
- `packages/nodes-base/nodes/Mandrill/Mandrill.node.ts`
- `packages/nodes-base/nodes/ManualTrigger/ManualTrigger.node.ts`
- `packages/nodes-base/nodes/Markdown/Markdown.node.ts`
- `packages/nodes-base/nodes/Marketstack/Marketstack.node.ts`
- `packages/nodes-base/nodes/Matrix/Matrix.node.ts`
- `packages/nodes-base/nodes/Mattermost/Mattermost.node.ts`
- `packages/nodes-base/nodes/Mattermost/v1/MattermostV1.node.ts`
- `packages/nodes-base/nodes/Mautic/Mautic.node.ts`
- `packages/nodes-base/nodes/Mautic/MauticTrigger.node.ts`
- `packages/nodes-base/nodes/Medium/Medium.node.ts`
- `packages/nodes-base/nodes/Merge/Merge.node.ts`
- `packages/nodes-base/nodes/Merge/v1/MergeV1.node.ts`
- `packages/nodes-base/nodes/Merge/v2/MergeV2.node.ts`
- `packages/nodes-base/nodes/Merge/v3/MergeV3.node.ts`
- `packages/nodes-base/nodes/MessageBird/MessageBird.node.ts`
- `packages/nodes-base/nodes/Metabase/Metabase.node.ts`
- `packages/nodes-base/nodes/Microsoft/Dynamics/MicrosoftDynamicsCrm.node.ts`
- `packages/nodes-base/nodes/Microsoft/Excel/MicrosoftExcel.node.ts`
- `packages/nodes-base/nodes/Microsoft/Excel/v1/MicrosoftExcelV1.node.ts`
- `packages/nodes-base/nodes/Microsoft/Excel/v2/MicrosoftExcelV2.node.ts`
- `packages/nodes-base/nodes/Microsoft/GraphSecurity/MicrosoftGraphSecurity.node.ts`
- `packages/nodes-base/nodes/Microsoft/OneDrive/MicrosoftOneDrive.node.ts`
- `packages/nodes-base/nodes/Microsoft/OneDrive/MicrosoftOneDriveTrigger.node.ts`
- `packages/nodes-base/nodes/Microsoft/Outlook/MicrosoftOutlook.node.ts`
- `packages/nodes-base/nodes/Microsoft/Outlook/MicrosoftOutlookTrigger.node.ts`
- `packages/nodes-base/nodes/Microsoft/Outlook/v1/MicrosoftOutlookV1.node.ts`
- `packages/nodes-base/nodes/Microsoft/Outlook/v2/MicrosoftOutlookV2.node.ts`
- `packages/nodes-base/nodes/Microsoft/Sql/MicrosoftSql.node.ts`
- `packages/nodes-base/nodes/Microsoft/Teams/MicrosoftTeams.node.ts`
- `packages/nodes-base/nodes/Microsoft/Teams/v1/MicrosoftTeamsV1.node.ts`
- `packages/nodes-base/nodes/Microsoft/Teams/v2/MicrosoftTeamsV2.node.ts`
- `packages/nodes-base/nodes/Microsoft/ToDo/MicrosoftToDo.node.ts`
- `packages/nodes-base/nodes/Mindee/Mindee.node.ts`
- `packages/nodes-base/nodes/Misp/Misp.node.ts`
- `packages/nodes-base/nodes/Mocean/Mocean.node.ts`
- `packages/nodes-base/nodes/MondayCom/MondayCom.node.ts`
- `packages/nodes-base/nodes/MongoDb/MongoDb.node.ts`
- `packages/nodes-base/nodes/MonicaCrm/MonicaCrm.node.ts`
- `packages/nodes-base/nodes/MoveBinaryData/MoveBinaryData.node.ts`
- `packages/nodes-base/nodes/Msg91/Msg91.node.ts`
- `packages/nodes-base/nodes/MySql/MySql.node.ts`
- `packages/nodes-base/nodes/MySql/v1/MySqlV1.node.ts`
- `packages/nodes-base/nodes/MySql/v2/MySqlV2.node.ts`
- `packages/nodes-base/nodes/N8n/N8n.node.ts`
- `packages/nodes-base/nodes/N8nTrainingCustomerDatastore/N8nTrainingCustomerDatastore.node.ts`
- `packages/nodes-base/nodes/N8nTrainingCustomerMessenger/N8nTrainingCustomerMessenger.node.ts`
- `packages/nodes-base/nodes/N8nTrigger/N8nTrigger.node.ts`
- `packages/nodes-base/nodes/Nasa/Nasa.node.ts`
- `packages/nodes-base/nodes/Netlify/Netlify.node.ts`
- `packages/nodes-base/nodes/Netlify/NetlifyTrigger.node.ts`
- `packages/nodes-base/nodes/Netscaler/ADC/NetscalerAdc.node.ts`
- `packages/nodes-base/nodes/NextCloud/NextCloud.node.ts`
- `packages/nodes-base/nodes/NoOp/NoOp.node.ts`
- `packages/nodes-base/nodes/NocoDB/NocoDB.node.ts`
- `packages/nodes-base/nodes/Notion/Notion.node.ts`
- `packages/nodes-base/nodes/Notion/NotionTrigger.node.ts`
- `packages/nodes-base/nodes/Notion/v1/NotionV1.node.ts`
- `packages/nodes-base/nodes/Notion/v2/NotionV2.node.ts`
- `packages/nodes-base/nodes/Npm/Npm.node.ts`
- `packages/nodes-base/nodes/Odoo/Odoo.node.ts`
- `packages/nodes-base/nodes/Okta/Okta.node.ts`
- `packages/nodes-base/nodes/OneSimpleApi/OneSimpleApi.node.ts`
- `packages/nodes-base/nodes/Onfleet/Onfleet.node.ts`
- `packages/nodes-base/nodes/Onfleet/OnfleetTrigger.node.ts`
- `packages/nodes-base/nodes/OpenAi/OpenAi.node.ts`
- `packages/nodes-base/nodes/OpenThesaurus/OpenThesaurus.node.ts`
- `packages/nodes-base/nodes/OpenWeatherMap/OpenWeatherMap.node.ts`
- `packages/nodes-base/nodes/Orbit/Orbit.node.ts`
- `packages/nodes-base/nodes/Oura/Oura.node.ts`
- `packages/nodes-base/nodes/Paddle/Paddle.node.ts`
- `packages/nodes-base/nodes/PagerDuty/PagerDuty.node.ts`
- `packages/nodes-base/nodes/PayPal/PayPal.node.ts`
- `packages/nodes-base/nodes/PayPal/PayPalTrigger.node.ts`
- `packages/nodes-base/nodes/Peekalink/Peekalink.node.ts`
- `packages/nodes-base/nodes/Phantombuster/Phantombuster.node.ts`
- `packages/nodes-base/nodes/PhilipsHue/PhilipsHue.node.ts`
- `packages/nodes-base/nodes/Pipedrive/Pipedrive.node.ts`
- `packages/nodes-base/nodes/Pipedrive/PipedriveTrigger.node.ts`
- `packages/nodes-base/nodes/Plivo/Plivo.node.ts`
- `packages/nodes-base/nodes/PostBin/PostBin.node.ts`
- `packages/nodes-base/nodes/PostHog/PostHog.node.ts`
- `packages/nodes-base/nodes/Postgres/Postgres.node.ts`
- `packages/nodes-base/nodes/Postgres/PostgresTrigger.node.ts`
- `packages/nodes-base/nodes/Postgres/v1/PostgresV1.node.ts`
- `packages/nodes-base/nodes/Postgres/v2/PostgresV2.node.ts`
- `packages/nodes-base/nodes/Postmark/PostmarkTrigger.node.ts`
- `packages/nodes-base/nodes/ProfitWell/ProfitWell.node.ts`
- `packages/nodes-base/nodes/Pushbullet/Pushbullet.node.ts`
- `packages/nodes-base/nodes/Pushcut/Pushcut.node.ts`
- `packages/nodes-base/nodes/Pushcut/PushcutTrigger.node.ts`
- `packages/nodes-base/nodes/Pushover/Pushover.node.ts`
- `packages/nodes-base/nodes/QuestDb/QuestDb.node.ts`
- `packages/nodes-base/nodes/QuickBase/QuickBase.node.ts`
- `packages/nodes-base/nodes/QuickBooks/QuickBooks.node.ts`
- `packages/nodes-base/nodes/QuickChart/QuickChart.node.ts`
- `packages/nodes-base/nodes/RabbitMQ/RabbitMQ.node.ts`
- `packages/nodes-base/nodes/RabbitMQ/RabbitMQTrigger.node.ts`
- `packages/nodes-base/nodes/Raindrop/Raindrop.node.ts`
- `packages/nodes-base/nodes/ReadBinaryFile/ReadBinaryFile.node.ts`
- `packages/nodes-base/nodes/ReadBinaryFiles/ReadBinaryFiles.node.ts`
- `packages/nodes-base/nodes/ReadPdf/ReadPDF.node.ts`
- `packages/nodes-base/nodes/Reddit/Reddit.node.ts`
- `packages/nodes-base/nodes/Redis/Redis.node.ts`
- `packages/nodes-base/nodes/Redis/RedisTrigger.node.ts`
- `packages/nodes-base/nodes/RenameKeys/RenameKeys.node.ts`
- `packages/nodes-base/nodes/RespondToWebhook/RespondToWebhook.node.ts`
- `packages/nodes-base/nodes/Rocketchat/Rocketchat.node.ts`
- `packages/nodes-base/nodes/RssFeedRead/RssFeedRead.node.ts`
- `packages/nodes-base/nodes/RssFeedRead/RssFeedReadTrigger.node.ts`
- `packages/nodes-base/nodes/Rundeck/Rundeck.node.ts`
- `packages/nodes-base/nodes/S3/S3.node.ts`
- `packages/nodes-base/nodes/Salesforce/Salesforce.node.ts`
- `packages/nodes-base/nodes/Salesforce/SalesforceTrigger.node.ts`
- `packages/nodes-base/nodes/Salesmate/Salesmate.node.ts`
- `packages/nodes-base/nodes/Schedule/ScheduleTrigger.node.ts`
- `packages/nodes-base/nodes/SeaTable/SeaTable.node.ts`
- `packages/nodes-base/nodes/SeaTable/SeaTableTrigger.node.ts`
- `packages/nodes-base/nodes/SecurityScorecard/SecurityScorecard.node.ts`
- `packages/nodes-base/nodes/Segment/Segment.node.ts`
- `packages/nodes-base/nodes/SendGrid/SendGrid.node.ts`
- `packages/nodes-base/nodes/Sendy/Sendy.node.ts`
- `packages/nodes-base/nodes/SentryIo/SentryIo.node.ts`
- `packages/nodes-base/nodes/ServiceNow/ServiceNow.node.ts`
- `packages/nodes-base/nodes/Set/Set.node.ts`
- `packages/nodes-base/nodes/Set/v1/SetV1.node.ts`
- `packages/nodes-base/nodes/Set/v2/SetV2.node.ts`
- `packages/nodes-base/nodes/Shopify/Shopify.node.ts`
- `packages/nodes-base/nodes/Shopify/ShopifyTrigger.node.ts`
- `packages/nodes-base/nodes/Signl4/Signl4.node.ts`
- `packages/nodes-base/nodes/Simulate/Simulate.node.ts`
- `packages/nodes-base/nodes/Simulate/SimulateTrigger.node.ts`
- `packages/nodes-base/nodes/Slack/Slack.node.ts`
- `packages/nodes-base/nodes/Slack/SlackTrigger.node.ts`
- `packages/nodes-base/nodes/Slack/V1/SlackV1.node.ts`
- `packages/nodes-base/nodes/Slack/V2/SlackV2.node.ts`
- `packages/nodes-base/nodes/Sms77/Sms77.node.ts`
- `packages/nodes-base/nodes/Snowflake/Snowflake.node.ts`
- `packages/nodes-base/nodes/SplitInBatches/SplitInBatches.node.ts`
- `packages/nodes-base/nodes/SplitInBatches/v1/SplitInBatchesV1.node.ts`
- `packages/nodes-base/nodes/SplitInBatches/v2/SplitInBatchesV2.node.ts`
- `packages/nodes-base/nodes/SplitInBatches/v3/SplitInBatchesV3.node.ts`
- `packages/nodes-base/nodes/Splunk/Splunk.node.ts`
- `packages/nodes-base/nodes/Splunk/v1/SplunkV1.node.ts`
- `packages/nodes-base/nodes/Splunk/v2/SplunkV2.node.ts`
- `packages/nodes-base/nodes/Spontit/Spontit.node.ts`
- `packages/nodes-base/nodes/Spotify/Spotify.node.ts`
- `packages/nodes-base/nodes/SpreadsheetFile/SpreadsheetFile.node.ts`
- `packages/nodes-base/nodes/SpreadsheetFile/v1/SpreadsheetFileV1.node.ts`
- `packages/nodes-base/nodes/SpreadsheetFile/v2/SpreadsheetFileV2.node.ts`
- `packages/nodes-base/nodes/SseTrigger/SseTrigger.node.ts`
- `packages/nodes-base/nodes/Ssh/Ssh.node.ts`
- `packages/nodes-base/nodes/Stackby/Stackby.node.ts`
- `packages/nodes-base/nodes/Start/Start.node.ts`
- `packages/nodes-base/nodes/StickyNote/StickyNote.node.ts`
- `packages/nodes-base/nodes/StopAndError/StopAndError.node.ts`
- `packages/nodes-base/nodes/Storyblok/Storyblok.node.ts`
- `packages/nodes-base/nodes/Strapi/Strapi.node.ts`
- `packages/nodes-base/nodes/Strava/Strava.node.ts`
- `packages/nodes-base/nodes/Strava/StravaTrigger.node.ts`
- `packages/nodes-base/nodes/Stripe/Stripe.node.ts`
- `packages/nodes-base/nodes/Stripe/StripeTrigger.node.ts`
- `packages/nodes-base/nodes/Supabase/Supabase.node.ts`
- `packages/nodes-base/nodes/SurveyMonkey/SurveyMonkeyTrigger.node.ts`
- `packages/nodes-base/nodes/Switch/Switch.node.ts`
- `packages/nodes-base/nodes/Switch/V1/SwitchV1.node.ts`
- `packages/nodes-base/nodes/Switch/V2/SwitchV2.node.ts`
- `packages/nodes-base/nodes/Switch/V3/SwitchV3.node.ts`
- `packages/nodes-base/nodes/SyncroMSP/SyncroMsp.node.ts`
- `packages/nodes-base/nodes/SyncroMSP/v1/SyncroMspV1.node.ts`
- `packages/nodes-base/nodes/Taiga/Taiga.node.ts`
- `packages/nodes-base/nodes/Taiga/TaigaTrigger.node.ts`
- `packages/nodes-base/nodes/Tapfiliate/Tapfiliate.node.ts`
- `packages/nodes-base/nodes/Telegram/Telegram.node.ts`
- `packages/nodes-base/nodes/Telegram/TelegramTrigger.node.ts`
- `packages/nodes-base/nodes/TheHive/TheHive.node.ts`
- `packages/nodes-base/nodes/TheHive/TheHiveTrigger.node.ts`
- `packages/nodes-base/nodes/TheHiveProject/TheHiveProject.node.ts`
- `packages/nodes-base/nodes/TheHiveProject/TheHiveProjectTrigger.node.ts`
- `packages/nodes-base/nodes/TimescaleDb/TimescaleDb.node.ts`
- `packages/nodes-base/nodes/Todoist/Todoist.node.ts`
- `packages/nodes-base/nodes/Todoist/v1/TodoistV1.node.ts`
- `packages/nodes-base/nodes/Todoist/v2/TodoistV2.node.ts`
- `packages/nodes-base/nodes/Toggl/TogglTrigger.node.ts`
- `packages/nodes-base/nodes/Totp/Totp.node.ts`
- `packages/nodes-base/nodes/Transform/Aggregate/Aggregate.node.ts`
- `packages/nodes-base/nodes/Transform/Limit/Limit.node.ts`
- `packages/nodes-base/nodes/Transform/RemoveDuplicates/RemoveDuplicates.node.ts`
- `packages/nodes-base/nodes/Transform/RemoveDuplicates/v1/RemoveDuplicatesV1.node.ts`
- `packages/nodes-base/nodes/Transform/RemoveDuplicates/v2/RemoveDuplicatesV2.node.ts`
- `packages/nodes-base/nodes/Transform/Sort/Sort.node.ts`
- `packages/nodes-base/nodes/Transform/SplitOut/SplitOut.node.ts`
- `packages/nodes-base/nodes/Transform/Summarize/Summarize.node.ts`
- `packages/nodes-base/nodes/TravisCi/TravisCi.node.ts`
- `packages/nodes-base/nodes/Trello/Trello.node.ts`
- `packages/nodes-base/nodes/Trello/TrelloTrigger.node.ts`
- `packages/nodes-base/nodes/Twake/Twake.node.ts`
- `packages/nodes-base/nodes/Twilio/Twilio.node.ts`
- `packages/nodes-base/nodes/Twilio/TwilioTrigger.node.ts`
- `packages/nodes-base/nodes/Twist/Twist.node.ts`
- `packages/nodes-base/nodes/Twitter/Twitter.node.ts`
- `packages/nodes-base/nodes/Twitter/V1/TwitterV1.node.ts`
- `packages/nodes-base/nodes/Twitter/V2/TwitterV2.node.ts`
- `packages/nodes-base/nodes/Typeform/TypeformTrigger.node.ts`
- `packages/nodes-base/nodes/UProc/UProc.node.ts`
- `packages/nodes-base/nodes/UnleashedSoftware/UnleashedSoftware.node.ts`
- `packages/nodes-base/nodes/Uplead/Uplead.node.ts`
- `packages/nodes-base/nodes/UptimeRobot/UptimeRobot.node.ts`
- `packages/nodes-base/nodes/UrlScanIo/UrlScanIo.node.ts`
- `packages/nodes-base/nodes/Venafi/Datacenter/VenafiTlsProtectDatacenter.node.ts`
- `packages/nodes-base/nodes/Venafi/Datacenter/VenafiTlsProtectDatacenterTrigger.node.ts`
- `packages/nodes-base/nodes/Venafi/ProtectCloud/VenafiTlsProtectCloud.node.ts`
- `packages/nodes-base/nodes/Venafi/ProtectCloud/VenafiTlsProtectCloudTrigger.node.ts`
- `packages/nodes-base/nodes/Vero/Vero.node.ts`
- `packages/nodes-base/nodes/Vonage/Vonage.node.ts`
- `packages/nodes-base/nodes/Wait/Wait.node.ts`
- `packages/nodes-base/nodes/Webflow/V1/WebflowTriggerV1.node.ts`
- `packages/nodes-base/nodes/Webflow/V1/WebflowV1.node.ts`
- `packages/nodes-base/nodes/Webflow/V2/WebflowTriggerV2.node.ts`
- `packages/nodes-base/nodes/Webflow/V2/WebflowV2.node.ts`
- `packages/nodes-base/nodes/Webflow/Webflow.node.ts`
- `packages/nodes-base/nodes/Webflow/WebflowTrigger.node.ts`
- `packages/nodes-base/nodes/Webhook/Webhook.node.ts`
- `packages/nodes-base/nodes/Wekan/Wekan.node.ts`
- `packages/nodes-base/nodes/WhatsApp/WhatsApp.node.ts`
- `packages/nodes-base/nodes/WhatsApp/WhatsAppTrigger.node.ts`
- `packages/nodes-base/nodes/Wise/Wise.node.ts`
- `packages/nodes-base/nodes/Wise/WiseTrigger.node.ts`
- `packages/nodes-base/nodes/WooCommerce/WooCommerce.node.ts`
- `packages/nodes-base/nodes/WooCommerce/WooCommerceTrigger.node.ts`
- `packages/nodes-base/nodes/Wordpress/Wordpress.node.ts`
- `packages/nodes-base/nodes/Workable/WorkableTrigger.node.ts`
- `packages/nodes-base/nodes/WorkflowTrigger/WorkflowTrigger.node.ts`
- `packages/nodes-base/nodes/WriteBinaryFile/WriteBinaryFile.node.ts`
- `packages/nodes-base/nodes/Wufoo/WufooTrigger.node.ts`
- `packages/nodes-base/nodes/Xero/Xero.node.ts`
- `packages/nodes-base/nodes/Xml/Xml.node.ts`
- `packages/nodes-base/nodes/Yourls/Yourls.node.ts`
- `packages/nodes-base/nodes/Zammad/Zammad.node.ts`
- `packages/nodes-base/nodes/Zendesk/Zendesk.node.ts`
- `packages/nodes-base/nodes/Zendesk/ZendeskTrigger.node.ts`
- `packages/nodes-base/nodes/Zoho/ZohoCrm.node.ts`
- `packages/nodes-base/nodes/Zoom/Zoom.node.ts`
- `packages/nodes-base/nodes/Zulip/Zulip.node.ts`

## Full listing — `@n8n/nodes-langchain` (`*.node.ts`)

Sorted alphabetically by path (79 entries).

- `packages/@n8n/nodes-langchain/nodes/agents/Agent/Agent.node.ts`
- `packages/@n8n/nodes-langchain/nodes/agents/OpenAiAssistant/OpenAiAssistant.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/ChainLLM/ChainLlm.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/ChainRetrievalQA/ChainRetrievalQa.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/ChainSummarization/ChainSummarization.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/ChainSummarization/V1/ChainSummarizationV1.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/ChainSummarization/V2/ChainSummarizationV2.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/InformationExtractor/InformationExtractor.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/SentimentAnalysis/SentimentAnalysis.node.ts`
- `packages/@n8n/nodes-langchain/nodes/chains/TextClassifier/TextClassifier.node.ts`
- `packages/@n8n/nodes-langchain/nodes/code/Code.node.ts`
- `packages/@n8n/nodes-langchain/nodes/document_loaders/DocumentBinaryInputLoader/DocumentBinaryInputLoader.node.ts`
- `packages/@n8n/nodes-langchain/nodes/document_loaders/DocumentDefaultDataLoader/DocumentDefaultDataLoader.node.ts`
- `packages/@n8n/nodes-langchain/nodes/document_loaders/DocumentGithubLoader/DocumentGithubLoader.node.ts`
- `packages/@n8n/nodes-langchain/nodes/document_loaders/DocumentJSONInputLoader/DocumentJsonInputLoader.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsAwsBedrock/EmbeddingsAwsBedrock.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsAzureOpenAi/EmbeddingsAzureOpenAi.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsCohere/EmbeddingsCohere.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsGoogleGemini/EmbeddingsGoogleGemini.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsHuggingFaceInference/EmbeddingsHuggingFaceInference.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsMistralCloud/EmbeddingsMistralCloud.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsOllama/EmbeddingsOllama.node.ts`
- `packages/@n8n/nodes-langchain/nodes/embeddings/EmbeddingsOpenAI/EmbeddingsOpenAi.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LMChatAnthropic/LmChatAnthropic.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LMChatOllama/LmChatOllama.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LMChatOpenAi/LmChatOpenAi.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LMCohere/LmCohere.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LMOllama/LmOllama.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LMOpenAi/LmOpenAi.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LMOpenHuggingFaceInference/LmOpenHuggingFaceInference.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LmChatAwsBedrock/LmChatAwsBedrock.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LmChatAzureOpenAi/LmChatAzureOpenAi.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LmChatGoogleGemini/LmChatGoogleGemini.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LmChatGoogleVertex/LmChatGoogleVertex.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LmChatGroq/LmChatGroq.node.ts`
- `packages/@n8n/nodes-langchain/nodes/llms/LmChatMistralCloud/LmChatMistralCloud.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryBufferWindow/MemoryBufferWindow.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryChatRetriever/MemoryChatRetriever.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryManager/MemoryManager.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryMotorhead/MemoryMotorhead.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryPostgresChat/MemoryPostgresChat.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryRedisChat/MemoryRedisChat.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryXata/MemoryXata.node.ts`
- `packages/@n8n/nodes-langchain/nodes/memory/MemoryZep/MemoryZep.node.ts`
- `packages/@n8n/nodes-langchain/nodes/output_parser/OutputParserAutofixing/OutputParserAutofixing.node.ts`
- `packages/@n8n/nodes-langchain/nodes/output_parser/OutputParserItemList/OutputParserItemList.node.ts`
- `packages/@n8n/nodes-langchain/nodes/output_parser/OutputParserStructured/OutputParserStructured.node.ts`
- `packages/@n8n/nodes-langchain/nodes/retrievers/RetrieverContextualCompression/RetrieverContextualCompression.node.ts`
- `packages/@n8n/nodes-langchain/nodes/retrievers/RetrieverMultiQuery/RetrieverMultiQuery.node.ts`
- `packages/@n8n/nodes-langchain/nodes/retrievers/RetrieverVectorStore/RetrieverVectorStore.node.ts`
- `packages/@n8n/nodes-langchain/nodes/retrievers/RetrieverWorkflow/RetrieverWorkflow.node.ts`
- `packages/@n8n/nodes-langchain/nodes/text_splitters/TextSplitterCharacterTextSplitter/TextSplitterCharacterTextSplitter.node.ts`
- `packages/@n8n/nodes-langchain/nodes/text_splitters/TextSplitterRecursiveCharacterTextSplitter/TextSplitterRecursiveCharacterTextSplitter.node.ts`
- `packages/@n8n/nodes-langchain/nodes/text_splitters/TextSplitterTokenSplitter/TextSplitterTokenSplitter.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolCalculator/ToolCalculator.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolCode/ToolCode.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolHttpRequest/ToolHttpRequest.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolSerpApi/ToolSerpApi.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolVectorStore/ToolVectorStore.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolWikipedia/ToolWikipedia.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolWolframAlpha/ToolWolframAlpha.node.ts`
- `packages/@n8n/nodes-langchain/nodes/tools/ToolWorkflow/ToolWorkflow.node.ts`
- `packages/@n8n/nodes-langchain/nodes/trigger/ChatTrigger/ChatTrigger.node.ts`
- `packages/@n8n/nodes-langchain/nodes/trigger/ManualChatTrigger/ManualChatTrigger.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreInMemory/VectorStoreInMemory.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreInMemoryInsert/VectorStoreInMemoryInsert.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreInMemoryLoad/VectorStoreInMemoryLoad.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStorePGVector/VectorStorePGVector.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStorePinecone/VectorStorePinecone.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStorePineconeInsert/VectorStorePineconeInsert.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStorePineconeLoad/VectorStorePineconeLoad.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreQdrant/VectorStoreQdrant.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreSupabase/VectorStoreSupabase.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreSupabaseInsert/VectorStoreSupabaseInsert.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreSupabaseLoad/VectorStoreSupabaseLoad.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreZep/VectorStoreZep.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreZepInsert/VectorStoreZepInsert.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vector_store/VectorStoreZepLoad/VectorStoreZepLoad.node.ts`
- `packages/@n8n/nodes-langchain/nodes/vendors/OpenAi/OpenAi.node.ts`

## Related folders (not enumerated here)

- **Credentials**: `../n8n/packages/nodes-base/credentials/` (and `@n8n/nodes-langchain/credentials/`).
- **Editor UI palette / nodes panel**: Vue app under [`../n8n/packages/editor-ui/`](../../n8n/packages/editor-ui/) (node discovery consumes generated metadata after build).
- **Workflow typing / shared models**: [`../n8n/packages/workflow/`](../../n8n/packages/workflow/).

## Appendix: format of `*.node.ts` node definitions

Every `*.node.ts` file under the packages listed above is a TypeScript module that **exports one node class**. It compiles into `dist/` and is loaded like any other integration. The authoring source is **always** the `*.node.ts`; runtime uses the emitted JS.

Primary types live in **`n8n-workflow`** (source: [`packages/workflow/src/Interfaces.ts`](../../n8n/packages/workflow/src/Interfaces.ts) in this monorepo).

### `INodeType`

A concrete integration implements **`INodeType`**, which ties together:

- **`description`** (required) — **`INodeTypeDescription`** (see below): manifest for the palette, versioning, NDV parameters, credential wiring, webhooks/triggers hints, declarative routing, etc.
- **`execute`** — normal action nodes: use `this` as **`IExecuteFunctions`**, call `this.getInputData()`, `this.getNodeParameter()`, return **`INodeExecutionData[][]`** (rows per output branch).
- **`trigger`**, **`poll`**, **`webhook`** — event-driven / scheduled / inbound HTTP entry points (only what that node uses).
- **`supplyData`** — nodes that expose data downstream without the usual execute path (advanced).
- **`methods`** — editor-time helpers referenced from **`description`**: **`loadOptions`**, **`listSearch`**, **`credentialTest`**, **`resourceMapping`**, **`actionHandler`**, keyed by string names wired from parameter definitions.
- **`webhookMethods`** — setup/teardown helpers for webhook subtypes (`default` vs `setup`).

### `INodeTypeDescription`

Extends **`INodeTypeBaseDescription`** (identity UI: **`displayName`**, internal **`name`**, **`group`**, **`icon`**, **`description`**, optional **`documentationUrl`**, **`defaultVersion`**, **`usableAsTool`**, etc.). The full description additionally includes:

- **`version`** — number or array of supported **`typeVersion`** values.
- **`defaults`** — e.g. default node instance **`name`** in the canvas (and deprecated **`color`**).
- **`inputs` / `outputs`** — typically **`Main`** **`NodeConnectionType`** or richer port configs; optionally expression-backed.
- **`properties`** — array of **`INodeProperties`**: NDV controls (`string`, `options`, resource/operation grids, **`displayOptions`**, **`routing`** for declarative HTTP, …).
- **`credentials`** — **`INodeCredentialDescription[]`** pointing at **`*.credentials.ts`** types by name.
- Optional: **`hooks`** (activate/deactivate), **`webhooks`**, **`requestDefaults`** / **`requestOperations`**, **`polling`**, **`triggerPanel`**, **`hints`**, etc.

Most “what the node looks like” and “how wires attach” lives in **`description`**; **`execute`** implements behavior.

### Common file patterns

**Single-version node** — **`class Foo implements INodeType`** with one **`description: INodeTypeDescription = { … }`** and **`async execute(this: IExecuteFunctions) { … }`**. Example sketch: **`Code`** in [`packages/nodes-base/nodes/Code/Code.node.ts`](../../n8n/packages/nodes-base/nodes/Code/Code.node.ts).

**Versioned node** — the top-level **`Xxx.node.ts`** extends **`VersionedNodeType`**: **`INodeTypeBaseDescription`** defines shared identity (**`displayName`**, **`name`**, **`icon`**, **`group`**); **`nodeVersions`** maps **`typeVersion`** keys to separate **`INodeType`** classes (**`SetV1`**, **`SetV2`**, …) so each slice can evolve its **`description`** and **`execute`** independently. Example: [`packages/nodes-base/nodes/Set/Set.node.ts`](../../n8n/packages/nodes-base/nodes/Set/Set.node.ts).

### Other files beside `*.node.ts`

Next to each node folder you usually find **`descriptions/`** shards, **`V1/` / `V2/`** version dirs, **`*.svg`** (see **`description.icon`** **`file:`** refs), **`helpers`**, **`GenericFunctions`**, sibling credential packages under **`packages/nodes-base/credentials/`**, and generated **`dist/`** plus metadata after **`pnpm build`** in that package.

For the canonical field-by-field **`INodeType`** / **`INodeTypeDescription`** contracts, grep or read **`packages/workflow`** `Interfaces.ts` as linked above rather than copying large interface blocks here (they churn between n8n releases).

## Appendix: DocRouter flow node definitions vs n8n `*.node.ts`

This repo’s **flows** feature is a separate engine from n8n (see also [`flows_workflow_interop.md`](./flows_workflow_interop.md)). Below is how **DocRouter node types** line up with **n8n node definitions** conceptually.

### Same idea at a high level

Both systems model: a **named node type** (`name` / **`key`**) with **palette metadata**, **how parameters are edited**, **how inputs/outputs wire**, and **how execution runs**.

| Concern | n8n (`*.node.ts`) | DocRouter |
|--------|-------------------|-----------|
| **Runtime / packaging** | TypeScript **`INodeType`** in `nodes-base` (or langchain), compiled to **`dist/`** | Python classes implementing the **`NodeType` protocol**, registered in-memory via **`ad.flows.register()`** at app startup |
| **Palette / list API** | `description.displayName`, `description.name`, icons, `group`, etc. | **`key`**, **`label`**, **`description`**, **`category`**, **`icon_key`**, port counts — returned by [`GET .../flows/node-types`](../packages/python/app/routes/flows.py) from each registered type |
| **Instance on the graph** | Workflow node JSON (type + parameters + position + connections) | **`FlowNode`** in a revision: **`type`** matches **`key`**, **`parameters`** is a JSON object, plus **`id`**, **`name`**, **`position`**, etc. (TypeScript: [`packages/typescript/sdk/src/types/flows.ts`](../packages/typescript/sdk/src/types/flows.ts)) |

DocRouter **`NodeType`** contract (Python): [`packages/python/analytiq_data/flows/node_registry.py`](../packages/python/analytiq_data/flows/node_registry.py). Example built-in implementations: [`packages/python/analytiq_data/flows/nodes/`](../packages/python/analytiq_data/flows/nodes/) and product nodes under [`packages/python/analytiq_data/docrouter_flows/nodes/`](../packages/python/analytiq_data/docrouter_flows/nodes/). Registration entry points: **`register_builtin_nodes()`** and **`register_docrouter_nodes()`** in the same areas.

### Important differences

#### 1. Parameters / “node detail view” (NDV)

- **n8n**: Large **`properties: INodeProperties[]`** arrays — field **types**, **displayOptions**, declarative **HTTP routing**, **`loadOptions`**, resource/operation UX, etc., all live in TS next to **`execute`**.
- **DocRouter**: A single **`parameter_schema`** per type — a **JSON Schema**-shaped dict. The frontend largely **reflects** that schema into generic controls (e.g. [`flowNodeConfigFields.tsx`](../packages/typescript/frontend/src/components/flows/flowNodeConfigFields.tsx)). There is no equivalent of n8n’s full **`INodePropertyRouting`** surface in DocRouter today.

**Net:** n8n favors **hand-built** parameter UIs per integration; DocRouter favors **schema-driven** forms with fewer bespoke UI primitives.

#### 2. Ports and connections

- **n8n**: **`inputs` / `outputs`** as **`NodeConnectionType`** (and optional richer port configurations).
- **DocRouter**: **`min_inputs`**, **`max_inputs`**, **`outputs`**, **`output_labels`**, **`is_merge`**; graph shape uses **`FlowConnections`** keyed by node id with **`main`**-style connection lists — not the same model as multiple non-main rails in n8n.

#### 3. Versioning of node *definitions*

- **n8n**: First-class **`VersionedNodeType`** and **`typeVersion`** on **`description`**.
- **DocRouter**: Revisions carry **`engine_version`**; each canvas node’s **`type`** is a string **`key`**. Evolving a node type is implicit in Python code and API compatibility, not parallel `V1`/`V2` TS classes per key.

#### 4. Execution runtime

- **n8n**: **`execute(this: IExecuteFunctions)`** in JavaScript/TypeScript with rich helpers, binary handling, sub-workflows, etc.
- **DocRouter**: **`async execute(context, node, inputs) -> outputs`** in Python with **`ExecutionContext`** and **`FlowItem`** payloads; some nodes use flags like **`batch_execute_inputs`** on the class. The platform is DocRouter services, not a generic SaaS HTTP integration layer like n8n’s.

#### 5. Ecosystem extension

- **n8n**: Hundreds of integrations in **`n8n-nodes-base`** (+ langchain); third parties ship TS nodes.
- **DocRouter**: A **small**, curated set (**`flows.*`** builtins + **`docrouter.*`** nodes). Extension means **new Python **`NodeType`** classes** + **`register()`**, not new **`*.node.ts`** files.

### Short summary

| | n8n | DocRouter |
|---|-----|-----------|
| **Definition artifact** | `*.node.ts` → **`INodeType`** | Python class → **`NodeType`** protocol |
| **UI spec** | **`INodeTypeDescription.properties`** | **`parameter_schema`** (JSON Schema) |
| **Graph instance** | n8n workflow node | **`FlowNode`** + **`FlowRevision`** |
| **Strength** | Per-node UX & integrations at scale | Simpler contract, Python-native engine, tighter product scope |

For n8n’s type contracts, prefer reading **[`Interfaces.ts`](../../n8n/packages/workflow/src/Interfaces.ts)** in **`../n8n`**; for DocRouter, **`node_registry.py`** and **`FlowsCodeNode`**-style examples in **`packages/python/analytiq_data/flows/nodes/`**.

For the programmatic pipeline that converts n8n nodes into DocRouter node packages, see **[`n8n_port_guide.md`](./n8n_port_guide.md)**.

