#!/usr/bin/env ruby
require 'cbor-diagnostic'
require 'cbor-packed'
require 'cbor-deterministic'
require 'cbor-canonical'
require 'pp'

SI_UNITS = %w[B kB MB GB TB PB EB ZB YB]

def human_size(bytes, decimals: 3)
  return "0 B" if bytes.zero?
  exp = [8, (Math.log(bytes) / Math.log(1000)).to_i].min # Prevent overflow
  value = bytes / (1000.0 ** exp)
  decimals_adjusted = decimals - Math.log10(value).floor
  "#{value.round(decimals_adjusted)} #{SI_UNITS[exp]}"
end

ARGF.binmode
i = ARGF.read
puts "Total size of CBOR input: #{human_size(i.bytesize)}"

o = CBOR.decode(i)

unpacked_count = Hash.new(0)
total_strings = 0
total_string_size = 0

o.cbor_visit do |item|
  if String === item
    unpacked_count[item] += 1
    total_string_size += item.bytesize
    total_strings += 1
  end
  true # continue visiting
end

fail unless unpacked_count.values.sum == total_strings

puts "Total byte size of string items: #{human_size(total_string_size)}"
puts "Total number of string items: #{total_strings}"
puts "Total number of different string values: #{unpacked_count.size}"
puts "Average size of string item: #{human_size(total_string_size.to_f / total_strings)}"
puts "Average occurrence frequency of string item: #{total_strings / unpacked_count.size.to_f}"
puts

once, multiple = unpacked_count.partition {|k, v| v == 1}

# Assume we need ~ 4 bytes of overhead for each use of a shared string
shared_savings = multiple.map{|k, v| [0, k.bytesize-4].max * v-1}.sum

puts "Approximate potential savings by string sharing: #{human_size(shared_savings)}"

## const. Analysis

const = {}
ctypes = Hash.new(0)

File.open("cospdx.cddl") do |f|
  f.each_line do |l|
    if /\A(?<ctype>(?:const|label)).(?<cname>\S+)\s*=\s*(?<cvalue>\S+)\s*\z/ =~ l
      ctypes[ctype] += 1
      puts ["dup", cname, const[cname], [ctype, cvalue]].inspect if const[cname] # XXX
      const[cname] = [ctype, cvalue]
    end
  end
end

pp ctypes                       # XXX

covered, uncovered = unpacked_count.partition {|k, v| const[k]}

puts
puts "Number of string values covered by label.* or const.*: #{covered.size}"
puts "Number of string values not covered by label.* or const.*: #{uncovered.size}"
puts "Number of string items covered by label.* or const.*: #{covered.map{|name, count| count}.sum}"
puts "Number of string item bytes covered by label.* or const.*: #{human_size(covered.map{|name, count| count*name.bytesize}.sum)}"
puts "Top 15 matches by total bytesize:"
pp covered.sort_by {|k, v| -v*k.bytesize}[0...15].map{|name, count| [name, count, human_size(count*name.bytesize)] }
# pp uncovered

## Hex Tail Analysis

puts

hex_tail_count = Hash.new(0)
hex_tail_size_count = Hash.new(0)

[["single", once], ["multiple", multiple]].each do |name, part|
  puts "Number of string values with #{name} occurrences: #{part.size}"
  keys = Hash[part].keys
  # pp keys
  keys.each do |key|
    if /(?<hexpart>(?:[0-9a-fA-F][0-9a-fA-F]){20,})\z/ =~ key
      hex_tail_size_count[hexpart.bytesize] += 1
      hex_tail_count[hexpart.downcase] += 1
    end
  end
end

puts
puts "Hex tails >= 20 chars (chars => number of tails of this size): #{hex_tail_size_count.sort}"
tail_hex_savings = hex_tail_size_count.map{(_1 - 4) * _2 / 2}.sum
puts "Approximate potential savings by representing hex tails as bytes: #{human_size(tail_hex_savings)}"

