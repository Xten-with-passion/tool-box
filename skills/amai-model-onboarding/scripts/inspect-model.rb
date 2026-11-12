#!/usr/bin/env ruby
# Read one YAML and emit only allowlisted metadata for exactly one model.
require 'yaml'
require 'json'

if ARGV.length != 2
  warn 'Usage: ruby inspect-model.rb <config.yaml> <model-id>'
  exit 2
end

begin
  document = YAML.safe_load(File.read(ARGV[0], encoding: 'UTF-8'),
                            permitted_classes: [], permitted_symbols: [], aliases: true)
  raise ArgumentError unless document.is_a?(Hash) && document['models'].is_a?(Array)

  matches = document['models'].select do |entry|
    raise ArgumentError unless entry.is_a?(Hash)
    entry['model_id'] == ARGV[1]
  end
  unless matches.length == 1
    warn "Expected exactly one model; found #{matches.length}."
    exit 1
  end

  model = matches.first
  %w[model_id model_name modality].each do |key|
    raise ArgumentError unless model[key].is_a?(String) && !model[key].strip.empty?
  end

  fields = %w[model_id model_name model_display_name vendor_name modality model_type
              disable model_disable free is_sync cost_type once_gen_image_num
              once_gen_video_num ref_image_param_type ref_video_param_type
              timeout_failed_minutes max_context_tokens max_completion_tokens
              support_vision support_video].freeze
  flags = %w[disable model_disable free is_sync support_vision support_video].freeze
  client_fields = %w[client_name model_name weight ref_image_param_type].freeze
  scalar = lambda do |value|
    value.nil? || value.is_a?(String) || value.is_a?(Numeric) || value == true || value == false
  end

  output = model.select { |key, _value| fields.include?(key) }
  output.each do |key, value|
    raise ArgumentError unless scalar.call(value)
    raise ArgumentError if flags.include?(key) && value != true && value != false
  end

  if model.key?('at')
    raise ArgumentError unless model['at'].is_a?(Hash)
    output['at'] = {}
    if model['at'].key?('enabled')
      enabled = model['at']['enabled']
      raise ArgumentError unless enabled == true || enabled == false
      output['at']['enabled'] = enabled
    end
  end

  if model.key?('clients')
    raise ArgumentError unless model['clients'].is_a?(Hash)
    output['clients'] = model['clients'].each_with_object({}) do |(group, clients), groups|
      raise ArgumentError unless group.is_a?(String) && clients.is_a?(Array)
      groups[group] = clients.map do |client|
        raise ArgumentError unless client.is_a?(Hash)
        selected = client.select { |key, _value| client_fields.include?(key) }
        selected.each_value { |value| raise ArgumentError unless scalar.call(value) }
        selected
      end
    end
  end

  # Do not descend into vendor definitions, credentials, URLs, or arbitrary fields.
  puts JSON.pretty_generate(output)
rescue StandardError => error
  # YAML errors can quote source lines containing credentials.
  warn "Model inspection failed (#{error.class}); source contents suppressed."
  exit 1
end
