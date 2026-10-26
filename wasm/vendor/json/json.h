#ifndef JSON_JSON_H_INCLUDED
#define JSON_JSON_H_INCLUDED

#include <string>
#include <map>
#include <vector>
#include <iostream>
#include <sstream>

#ifndef JSONCPP_STRING
#define JSONCPP_STRING std::string
#endif

namespace Json {

class Value {
public:
    enum Type {
        nullValue = 0,
        intValue,
        realValue,
        stringValue,
        booleanValue,
        arrayValue,
        objectValue
    };

    Value() : mType(nullValue), mInt(0), mBool(false) {}
    Value(int v) : mType(intValue), mInt(v), mBool(v != 0) {}
    Value(bool v) : mType(booleanValue), mInt(v ? 1 : 0), mBool(v) {}
    Value(const std::string &v) : mType(stringValue), mInt(0), mBool(false), mStr(v) {}
    Value(const char *v) : mType(stringValue), mInt(0), mBool(false), mStr(v ? v : "") {}

    Value& operator[](const std::string &key) {
        mType = objectValue;
        return mObj[key];
    }

    Value& operator[](const char *key) {
        return (*this)[std::string(key ? key : "")];
    }

    const Value& operator[](const std::string &key) const {
        auto it = mObj.find(key);
        if (it != mObj.end()) return it->second;
        static const Value nullVal;
        return nullVal;
    }

    bool isMember(const std::string &key) const {
        return mObj.find(key) != mObj.end();
    }

    Value get(const std::string &key, const Value &defaultValue) const {
        auto it = mObj.find(key);
        if (it != mObj.end()) return it->second;
        return defaultValue;
    }

    int asInt() const {
        if (mType == intValue) return mInt;
        if (mType == booleanValue) return mBool ? 1 : 0;
        if (mType == stringValue) {
            try { return std::stoi(mStr); } catch (...) { return 0; }
        }
        return 0;
    }

    bool asBool() const {
        if (mType == booleanValue) return mBool;
        if (mType == intValue) return mInt != 0;
        if (mType == stringValue) return (mStr == "true" || mStr == "1");
        return false;
    }

    std::string asString() const {
        if (mType == stringValue) return mStr;
        if (mType == intValue) return std::to_string(mInt);
        if (mType == booleanValue) return mBool ? "true" : "false";
        return "";
    }

    Type type() const { return mType; }
    const std::map<std::string, Value>& getObject() const { return mObj; }

    void writeTo(std::ostream &os, int indent = 0) const {
        std::string ind(indent * 2, ' ');
        if (mType == objectValue) {
            os << "{\n";
            size_t count = 0;
            for (const auto &pair : mObj) {
                os << ind << "  \"" << pair.first << "\": ";
                pair.second.writeTo(os, indent + 1);
                if (++count < mObj.size()) os << ",";
                os << "\n";
            }
            os << ind << "}";
        } else if (mType == stringValue) {
            os << "\"" << mStr << "\"";
        } else if (mType == intValue) {
            os << mInt;
        } else if (mType == booleanValue) {
            os << (mBool ? "true" : "false");
        } else {
            os << "null";
        }
    }

private:
    Type mType;
    int mInt;
    bool mBool;
    std::string mStr;
    std::map<std::string, Value> mObj;
};

inline std::ostream& operator<<(std::ostream &os, const Value &val) {
    val.writeTo(os);
    return os;
}

class CharReaderBuilder {
public:
    CharReaderBuilder() {}
};

bool parseFromStream(CharReaderBuilder const &, std::istream &is, Value *root, JSONCPP_STRING *errs);

} // namespace Json

#endif // JSON_JSON_H_INCLUDED
