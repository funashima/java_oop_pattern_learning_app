import java.util.Map;

/** Standalone Abstract Factory example; not part of Pattern Lab's event schema. */
public class CodecStudy {
    interface Encoder { String encode(int x); String family(); }
    interface Decoder { int decode(String s); String family(); }
    interface CodecFactory {
        Encoder createEncoder();
        Decoder createDecoder();
    }
    static final class DecimalEncoder implements Encoder {
        public String encode(int x) { return Integer.toString(x); }
        public String family() { return "decimal"; }
    }
    static final class HexEncoder implements Encoder {
        public String encode(int x) { return Integer.toHexString(x); }
        public String family() { return "hex"; }
    }
    static final class DecimalDecoder implements Decoder {
        public int decode(String s) { return Integer.parseInt(s, 10); }
        public String family() { return "decimal"; }
    }
    static final class HexDecoder implements Decoder {
        public int decode(String s) { return Integer.parseInt(s, 16); }
        public String family() { return "hex"; }
    }
    static final class FaultyHexDecoder implements Decoder {
        public int decode(String s) { return Integer.parseInt(s, 16) ^ 1; }
        public String family() { return "hex"; }
    }
    static final class DecimalFactory implements CodecFactory {
        public Encoder createEncoder() { return new DecimalEncoder(); }
        public Decoder createDecoder() { return new DecimalDecoder(); }
    }
    static final class HexFactory implements CodecFactory {
        public Encoder createEncoder() { return new HexEncoder(); }
        public Decoder createDecoder() { return new HexDecoder(); }
    }
    static final class MixedFactory implements CodecFactory {
        public Encoder createEncoder() { return new HexEncoder(); }
        public Decoder createDecoder() { return new DecimalDecoder(); }
    }
    static final class FaultyHexFactory implements CodecFactory {
        public Encoder createEncoder() { return new HexEncoder(); }
        public Decoder createDecoder() { return new FaultyHexDecoder(); }
    }
    // Only fixed labels and canonical nonnegative integer strings are printed.
    static String quote(String s) { return s == null ? "null" : "\"" + s + "\""; }
    static void trial(String name, String requested, CodecFactory factory, int x) {
        Encoder e = factory.createEncoder();
        Decoder d = factory.createDecoder();
        String encoded = e.encode(x);
        Integer decoded = null;
        String error = null;
        String rawError = null;
        try { decoded = d.decode(encoded); }
        catch (NumberFormatException ex) {
            error = "ParseError";
            rawError = ex.getClass().getSimpleName();
        }
        System.out.println("{\"kind\":\"trial\",\"case\":" + quote(name)
            + ",\"x\":" + x + ",\"requested\":" + quote(requested)
            + ",\"encoder_family\":" + quote(e.family())
            + ",\"decoder_family\":" + quote(d.family())
            + ",\"encoded\":" + quote(encoded) + ",\"decoded\":" + decoded
            + ",\"error\":" + quote(error) + ",\"raw_error\":" + quote(rawError) + "}");
    }
    public static void main(String[] args) {
        for (int x = 0; x <= 255; x++) {
            trial("decimal", "decimal", new DecimalFactory(), x);
            trial("hex", "hex", new HexFactory(), x);
            trial("mixed", "hex", new MixedFactory(), x);
            trial("wrong_family", "hex", new DecimalFactory(), x);
            trial("faulty_hex", "hex", new FaultyHexFactory(), x);
            String decimal = new DecimalEncoder().encode(x);
            String converted = new HexEncoder().encode(new DecimalDecoder().decode(decimal));
            System.out.println("{\"kind\":\"conversion\",\"x\":" + x
                + ",\"decimal\":" + quote(decimal) + ",\"hex\":" + quote(converted) + "}");
        }
        int max = Integer.MAX_VALUE;
        Map<String, Integer> left = new java.util.HashMap<>();
        Map<String, Integer> right = new java.util.HashMap<>();
        left.put("value", 0); right.put("value", 0);
        System.out.println("{\"kind\":\"boundary\",\"negative_division\":" + ((-1 * 8) / 10)
            + ",\"max_plus_one\":" + (max + 1)
            + ",\"value_equal\":" + left.equals(right)
            + ",\"same_identity\":" + (left == right) + "}");
    }
}
