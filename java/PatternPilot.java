import java.util.*;
import java.lang.reflect.*;

/** Four bounded, instrumented lessons. Not a general Java debugger. */
public class PatternPilot {
    static boolean broken;
    static int input;
    static String lesson;
    static final Probe p = new Probe();

    // LESSON references: two variables can refer to one object.
    static class Box { int value; }
    static class References { Box a; Box b; }
    static void references() {
        References r = new References(); p.add("refs", r);
        r.a = new Box(); p.add("box", r.a); p.set(r, "a", r.a);
        if (broken) { r.b = new Box(); p.add("copy", r.b); }
        else { r.b = r.a; }
        p.set(r, "b", r.b);
        p.checkpoint("alias");
        p.call(r, r.b, "write", input);
        r.b.value = input; p.set(r.b, "value", r.b.value);
        p.ret(r.b, r.b.value);
        p.checkpoint("write");
        p.result(map("a", r.a.value, "b", r.b.value, "same", r.a == r.b));
    }

    // LESSON strategy: declared type Price, runtime type Discount.
    interface Price { int quote(int amount); }
    static class Regular implements Price {
        public int quote(int amount) { return amount; }
    }
    static class Discount implements Price {
        public int quote(int amount) { return amount * 8 / 10; }
    }
    static class Checkout {
        Price price;
        int total;
        int quote(int amount, Price fallback) {
            Price selected = broken ? fallback : price;
            p.call(this, selected, "quote", amount);
            total = selected.quote(amount);
            p.ret(selected, total);
            p.set(this, "total", total);
            return total;
        }
    }
    static void strategy() {
        Checkout c = new Checkout(); p.add("context", c);
        Price regular = new Regular(); p.add("regular", regular);
        Price discount = new Discount(); p.add("discount", discount);
        c.price = regular; p.set(c, "price", c.price);
        p.checkpoint("regular");
        c.quote(input, regular); p.checkpoint("first_quote");
        c.price = discount; p.set(c, "price", c.price);
        p.checkpoint("switch");
        c.quote(input, regular); p.checkpoint("second_quote");
        p.result(map("total", c.total, "selected", p.id(c.price)));
    }

    // LESSON state: the state object handles the request and changes context.
    interface GateState { void handle(Gate g, GateState next); }
    static class Locked implements GateState {
        public void handle(Gate g, GateState next) {
            if (!broken) { g.state = next; p.set(g, "state", next); }
        }
    }
    static class Open implements GateState {
        public void handle(Gate g, GateState next) {
            g.passed++; p.set(g, "passed", g.passed);
            g.state = next; p.set(g, "state", next);
        }
    }
    static class Gate {
        GateState state;
        int passed;
        void request(GateState next) {
            GateState receiver = state;
            p.call(this, receiver, "handle", 0);
            receiver.handle(this, next);
            p.ret(receiver, passed);
        }
    }
    static void state() {
        Gate g = new Gate(); p.add("gate", g);
        GateState locked = new Locked(); p.add("locked", locked);
        GateState open = new Open(); p.add("open", open);
        g.state = locked; p.set(g, "state", locked);
        p.checkpoint("ready");
        g.request(open); p.checkpoint("unlock");
        g.request(locked); p.checkpoint("pass");
        p.result(map("passed", g.passed, "state", p.id(g.state)));
    }

    // LESSON observer: synchronous notifications; list unchanged during callback.
    interface Observer { void update(int value); }
    static class Display implements Observer {
        int value;
        int updates;
        public void update(int newValue) {
            value = newValue; updates++;
            p.set(this, "value", value); p.set(this, "updates", updates);
        }
    }
    static class Subject {
        List<Observer> listeners = new ArrayList<>();
        void subscribe(Observer o) { listeners.add(o); p.set(this, "listeners", listeners); }
        void remove(Observer o) { listeners.remove(o); p.set(this, "listeners", listeners); }
        void publish(int value, String cycle) {
            p.event("cycle_begin", map("cycle", cycle, "members", p.value(listeners), "input", value));
            for (int i = 0; i < listeners.size(); i++) {
                if (broken && i == listeners.size() - 1) continue;
                Observer o = listeners.get(i);
                p.call(this, o, "update", value);
                o.update(value); p.ret(o, value);
            }
            p.event("cycle_end", map("cycle", cycle));
        }
    }
    static void observer() {
        Subject s = new Subject(); p.add("subject", s);
        Observer a = new Display(); p.add("display_a", a);
        Observer b = new Display(); p.add("display_b", b);
        s.subscribe(a); s.subscribe(b); p.checkpoint("subscribed");
        s.publish(input, "first"); p.checkpoint("notified");
        s.remove(b); p.checkpoint("removed");
        s.publish(input + 1, "second"); p.checkpoint("notified_again");
        Display da = (Display) a, db = (Display) b;
        p.result(map("a_updates", da.updates, "b_updates", db.updates,
                     "a_value", da.value, "b_value", db.value));
    }

    public static void main(String[] args) {
        lesson = args.length > 0 ? args[0] : "strategy";
        String variant = args.length > 1 ? args[1] : "normal";
        if (!variant.equals("normal") && !variant.equals("broken")) throw new IllegalArgumentException("variant");
        broken = variant.equals("broken");
        input = args.length > 2 ? Integer.parseInt(args[2]) : 100;
        if (input < 0 || input > 10000) throw new IllegalArgumentException("input 0..10000");
        p.event("meta", map("schema", 1, "lesson", lesson, "variant", variant,
            "input", input, "java", System.getProperty("java.version")));
        switch (lesson) {
            case "references": references(); break;
            case "strategy": strategy(); break;
            case "state": state(); break;
            case "observer": observer(); break;
            default: throw new IllegalArgumentException("unknown lesson");
        }
        p.event("end", map("complete", true));
    }

    static Map<String,Object> map(Object... values) {
        Map<String,Object> m = new LinkedHashMap<>();
        for (int i=0;i<values.length;i+=2) m.put((String) values[i], values[i+1]);
        return m;
    }
    static class Probe {
        final IdentityHashMap<Object,String> ids = new IdentityHashMap<>();
        final LinkedHashMap<String,Object> objects = new LinkedHashMap<>();
        int seq;
        String id(Object o) {
            String id = ids.get(o);
            if (id == null) throw new IllegalStateException("unregistered object");
            return id;
        }
        Object value(Object o) {
            if (o == null || o instanceof Number || o instanceof Boolean || o instanceof String) return o;
            if (o instanceof Collection<?>) {
                List<Object> a = new ArrayList<>();
                for (Object e : (Collection<?>) o) a.add(value(e));
                return a;
            }
            return map("ref", id(o));
        }
        Map<String,Object> fields(Object o) {
            Map<String,Object> fields = new LinkedHashMap<>();
            try {
                for (Field f : o.getClass().getDeclaredFields()) {
                    if (Modifier.isStatic(f.getModifiers()) || f.isSynthetic()) continue;
                    f.setAccessible(true); fields.put(f.getName(), value(f.get(o)));
                }
            } catch (ReflectiveOperationException ex) { throw new RuntimeException(ex); }
            return fields;
        }
        void add(String name, Object o) {
            if (ids.containsKey(o) || objects.containsKey(name)) throw new IllegalStateException("duplicate id");
            ids.put(o, name); objects.put(name,o);
            event("new", map("id", name, "type", o.getClass().getSimpleName(), "fields", fields(o)));
        }
        void set(Object o, String field, Object value) {
            event("set", map("id", id(o), "field", field, "value", value(value)));
        }
        void call(Object from, Object to, String method, int arg) {
            event("call", map("from", id(from), "to", id(to), "method", method, "arg", arg));
        }
        void ret(Object from, int value) { event("return", map("from", id(from), "value", value)); }
        void checkpoint(String name) {
            // Direct reflection reads current business objects; never reads emitted events.
            Map<String,Object> observed = new LinkedHashMap<>();
            for (Map.Entry<String,Object> e : objects.entrySet())
                observed.put(e.getKey(), map("type",e.getValue().getClass().getSimpleName(),"fields",fields(e.getValue())));
            event("checkpoint", map("name", name, "observed", observed));
        }
        void result(Object result) { event("result", map("value", result)); }
        void event(String kind, Map<String,Object> data) {
            int line = 0;
            for (StackTraceElement e : Thread.currentThread().getStackTrace())
                if (e.getClassName().startsWith("PatternPilot") && !e.getClassName().equals("PatternPilot$Probe")) {
                    line=e.getLineNumber(); break;
                }
            Map<String,Object> e = map("seq", ++seq, "kind", kind, "line", line);
            e.putAll(data); System.out.println(json(e));
        }
    }
    static String json(Object v) {
        if (v == null) return "null";
        if (v instanceof Number || v instanceof Boolean) return v.toString();
        if (v instanceof Map<?,?>) {
            List<String> parts=new ArrayList<>();
            for (Map.Entry<?,?> e : ((Map<?,?>)v).entrySet()) parts.add(json(e.getKey().toString())+":"+json(e.getValue()));
            return "{"+String.join(",",parts)+"}";
        }
        if (v instanceof Collection<?>) {
            List<String> parts=new ArrayList<>(); for(Object x:(Collection<?>)v) parts.add(json(x));
            return "["+String.join(",",parts)+"]";
        }
        String s=v.toString(); StringBuilder out=new StringBuilder("\"");
        for(char c:s.toCharArray()) {
            if(c=='"'||c=='\\') out.append('\\').append(c);
            else if(c<32) out.append(String.format("\\u%04x",(int)c));
            else out.append(c);
        }
        return out.append('"').toString();
    }
}
