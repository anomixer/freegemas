#include "json/json.h"
#include <cctype>

namespace Json {

static void skipWhitespace(std::istream &is) {
    while (is.good() && std::isspace(is.peek())) {
        is.get();
    }
}

static std::string parseString(std::istream &is) {
    std::string s;
    if (is.get() != '"') return "";
    while (is.good()) {
        char c = is.get();
        if (c == '"') break;
        if (c == '\\') {
            if (!is.good()) break;
            c = is.get();
        }
        s.push_back(c);
    }
    return s;
}

static Value parseValue(std::istream &is);

static Value parseObject(std::istream &is) {
    Value obj;
    if (is.get() != '{') return obj;
    while (is.good()) {
        skipWhitespace(is);
        if (is.peek() == '}') {
            is.get();
            break;
        }
        std::string key = parseString(is);
        skipWhitespace(is);
        if (is.get() != ':') break;
        skipWhitespace(is);
        obj[key] = parseValue(is);
        skipWhitespace(is);
        char c = is.peek();
        if (c == ',') {
            is.get();
        } else if (c == '}') {
            is.get();
            break;
        }
    }
    return obj;
}

static Value parseValue(std::istream &is) {
    skipWhitespace(is);
    char c = is.peek();
    if (c == '{') {
        return parseObject(is);
    } else if (c == '"') {
        return Value(parseString(is));
    } else if (c == 't' || c == 'T') {
        std::string s;
        for (int i = 0; i < 4 && is.good(); ++i) s.push_back(is.get());
        return Value(true);
    } else if (c == 'f' || c == 'F') {
        std::string s;
        for (int i = 0; i < 5 && is.good(); ++i) s.push_back(is.get());
        return Value(false);
    } else if (std::isdigit(c) || c == '-') {
        int val = 0;
        is >> val;
        return Value(val);
    }
    return Value();
}

bool parseFromStream(CharReaderBuilder const &, std::istream &is, Value *root, JSONCPP_STRING *errs) {
    if (!root) return false;
    skipWhitespace(is);
    if (!is.good()) return false;
    *root = parseValue(is);
    return true;
}

} // namespace Json
