{#-
  Override of dbt's default schema-naming behaviour.

  By default, when a folder config says `+schema: staging`, dbt names the
  schema `<target_schema>_staging` (e.g. STAGING_STAGING) - a well-known
  gotcha. This override makes custom schema names pass through exactly as
  written, so our models land in clean schemas: STAGING and MARTS.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
